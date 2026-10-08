import React from 'react';
import { ShieldCheck, Zap, FileText } from 'lucide-react';

export default function ExecutiveSummary({ answer, confidence, executionTime }) {
  // Format text to highlight citation tags e.g. [JIRA-PAY-142]
  const renderFormattedAnswer = (text) => {
    if (!text) return null;
    const parts = text.split(/(\[[A-Z0-9-_\s]+\])/g);
    return parts.map((part, i) => {
      if (part.startsWith('[') && part.endsWith(']')) {
        return (
          <span 
            key={i} 
            style={{
              background: 'rgba(59, 130, 246, 0.18)',
              color: '#60A5FA',
              border: '1px solid rgba(59, 130, 246, 0.4)',
              padding: '2px 6px',
              borderRadius: '4px',
              fontWeight: 700,
              fontFamily: 'var(--font-mono)',
              fontSize: '0.82rem',
              margin: '0 2px'
            }}
          >
            {part}
          </span>
        );
      }
      return part;
    });
  };

  return (
    <div className="glass-card" style={{
      padding: '24px',
      marginBottom: '24px',
      borderLeft: '4px solid var(--border-highlight)'
    }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <FileText size={20} color="#60A5FA" />
          <h3 style={{ fontSize: '1.1rem', fontWeight: 700, margin: 0, color: '#F3F4F6' }}>
            Evidence-Backed Executive Answer
          </h3>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.8rem', color: '#10B981', background: 'rgba(16, 185, 129, 0.1)', padding: '4px 10px', borderRadius: '12px' }}>
            <ShieldCheck size={14} />
            <span>Confidence: <strong>{Math.round((confidence || 0.95) * 100)}%</strong></span>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '0.78rem', color: 'var(--text-muted)' }}>
            <Zap size={13} color="#F59E0B" />
            <span>{executionTime} ms</span>
          </div>
        </div>
      </div>

      <div style={{
        fontSize: '0.96rem',
        color: '#E5E7EB',
        lineHeight: '1.7',
        whiteSpace: 'pre-line'
      }}>
        {renderFormattedAnswer(answer)}
      </div>
    </div>
  );
}
