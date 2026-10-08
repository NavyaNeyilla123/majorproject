import React from 'react';
import { Cpu, Database, ExternalLink, Activity, Layers } from 'lucide-react';

export default function Header({ healthData, onReindex, isIngesting }) {
  const vectorCount = healthData?.vector_store?.indexed_vectors ?? 0;

  return (
    <header style={{
      background: 'rgba(17, 23, 38, 0.95)',
      backdropFilter: 'blur(12px)',
      borderBottom: '1px solid var(--border-color)',
      padding: '16px 32px',
      position: 'sticky',
      top: 0,
      zIndex: 100,
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between'
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
        <div style={{
          background: 'linear-gradient(135deg, #2563EB 0%, #7C3AED 100%)',
          width: '42px',
          height: '42px',
          borderRadius: '10px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          boxShadow: '0 4px 12px rgba(37, 99, 235, 0.4)'
        }}>
          <Layers size={24} color="#FFF" />
        </div>
        <div>
          <h1 style={{ fontSize: '1.25rem', fontWeight: 800, letterSpacing: '-0.3px', margin: 0 }}>
            KnowledgeOps <span className="gradient-text">AI</span>
          </h1>
          <p style={{ fontSize: '0.78rem', color: 'var(--text-muted)', margin: 0, fontWeight: 500 }}>
            AI-Powered Enterprise Project Intelligence Platform
          </p>
        </div>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: '12px',
          background: 'var(--bg-input)',
          padding: '6px 14px',
          borderRadius: '20px',
          border: '1px solid var(--border-color)',
          fontSize: '0.8rem'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span style={{
              width: '8px',
              height: '8px',
              borderRadius: '50%',
              background: '#10B981',
              boxShadow: '0 0 8px #10B981'
            }} />
            <span style={{ color: 'var(--text-muted)' }}>Engine:</span>
            <strong style={{ color: '#F3F4F6' }}>LangGraph + Gemini</strong>
          </div>
          <span style={{ color: 'var(--border-color)' }}>|</span>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <Database size={14} color="#60A5FA" />
            <span style={{ color: 'var(--text-muted)' }}>Qdrant:</span>
            <strong style={{ color: '#60A5FA' }}>{vectorCount} vectors</strong>
          </div>
        </div>

        <button 
          onClick={onReindex}
          disabled={isIngesting}
          className="btn-secondary"
          title="Re-Index Demo Enterprise Data"
        >
          <Activity size={15} className={isIngesting ? 'pulse-active' : ''} />
          {isIngesting ? 'Indexing Data...' : 'Sync Enterprise Data'}
        </button>

        <a 
          href="http://localhost:8000/docs" 
          target="_blank" 
          rel="noreferrer"
          className="btn-secondary"
          style={{ textDecoration: 'none' }}
        >
          <span>Swagger API</span>
          <ExternalLink size={14} />
        </a>
      </div>
    </header>
  );
}
