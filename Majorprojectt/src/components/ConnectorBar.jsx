import React from 'react';
import { GitPullRequest, CheckCircle2, MessageSquare, BookOpen, Layers } from 'lucide-react';

export default function ConnectorBar({ connectors }) {
  const getIcon = (type) => {
    switch (type) {
      case 'Jira': return <Layers size={18} color="#3B82F6" />;
      case 'GitHub': return <GitPullRequest size={18} color="#A855F7" />;
      case 'Confluence': return <BookOpen size={18} color="#10B981" />;
      case 'Slack': return <MessageSquare size={18} color="#F43F5E" />;
      default: return <CheckCircle2 size={18} color="#3B82F6" />;
    }
  };

  const getBadgeClass = (type) => {
    switch (type) {
      case 'Jira': return 'badge-jira';
      case 'GitHub': return 'badge-github';
      case 'Confluence': return 'badge-confluence';
      case 'Slack': return 'badge-slack';
      default: return 'badge-jira';
    }
  };

  return (
    <div style={{ marginBottom: '28px' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '12px' }}>
        <h3 style={{ fontSize: '0.88rem', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
          MCP Enterprise Connectors & Adapters (4 Connected)
        </h3>
        <span style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>
          Phase 7 & 8 Connector Abstraction Layer
        </span>
      </div>

      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(230px, 1fr))',
        gap: '16px'
      }}>
        {connectors.map((c, idx) => (
          <div key={idx} className="glass-card" style={{ padding: '16px', display: 'flex', alignItems: 'center', gap: '14px' }}>
            <div style={{
              background: 'var(--bg-input)',
              padding: '10px',
              borderRadius: '8px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center'
            }}>
              {getIcon(c.type)}
            </div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '4px' }}>
                <span className={`badge ${getBadgeClass(c.type)}`}>{c.type}</span>
                <span style={{ fontSize: '0.7rem', color: '#10B981', display: 'flex', alignItems: 'center', gap: '4px', fontWeight: 600 }}>
                  <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: '#10B981' }} />
                  ONLINE
                </span>
              </div>
              <p style={{ fontSize: '0.82rem', fontWeight: 600, color: '#F3F4F6', margin: 0, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                {c.mode}
              </p>
              <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
                {c.doc_count} items indexed
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
