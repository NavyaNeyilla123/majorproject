import React from 'react';
import { Search, Sparkles, HelpCircle } from 'lucide-react';

export default function QueryBox({ query, setQuery, onAnalyze, isLoading }) {
  const presets = [
    "Why is Sprint 5 delayed?",
    "What is blocking PAY-142?",
    "What are the payment API contract dependencies?",
    "Show developer discussions regarding checkout integration"
  ];

  const handleSubmit = (e) => {
    e.preventDefault();
    if (query.trim() && !isLoading) {
      onAnalyze(query);
    }
  };

  return (
    <div className="glass-card" style={{ padding: '24px', marginBottom: '28px' }}>
      <form onSubmit={handleSubmit}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px' }}>
          <Sparkles size={18} color="#60A5FA" />
          <h2 style={{ fontSize: '1rem', fontWeight: 700, margin: 0, color: '#F3F4F6' }}>
            Natural Language Enterprise Query
          </h2>
        </div>

        <div style={{
          display: 'flex',
          gap: '12px',
          background: 'var(--bg-input)',
          border: '1px solid var(--border-color)',
          borderRadius: '10px',
          padding: '6px 12px',
          alignItems: 'center'
        }}>
          <Search size={20} color="var(--text-muted)" />
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Ask a question about your project (e.g. Why is Sprint 5 delayed?)..."
            style={{
              flex: 1,
              background: 'transparent',
              border: 'none',
              color: '#F3F4F6',
              fontSize: '1rem',
              outline: 'none',
              padding: '10px 0'
            }}
          />
          <button 
            type="submit" 
            disabled={isLoading || !query.trim()}
            className="btn-primary"
          >
            {isLoading ? (
              <>
                <span className="pulse-active" style={{ display: 'inline-block', width: '12px', height: '12px', borderRadius: '50%', background: '#FFF' }} />
                <span>Correlating Sources...</span>
              </>
            ) : (
              <>
                <Sparkles size={16} />
                <span>Analyze Project</span>
              </>
            )}
          </button>
        </div>
      </form>

      <div style={{ marginTop: '16px', display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
        <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: '4px' }}>
          <HelpCircle size={13} />
          Suggested Questions:
        </span>
        {presets.map((preset, idx) => (
          <button
            key={idx}
            type="button"
            onClick={() => {
              setQuery(preset);
              onAnalyze(preset);
            }}
            style={{
              background: query === preset ? 'rgba(59, 130, 246, 0.2)' : 'var(--bg-input)',
              border: query === preset ? '1px solid #3B82F6' : '1px solid var(--border-color)',
              color: query === preset ? '#60A5FA' : 'var(--text-muted)',
              borderRadius: '20px',
              padding: '4px 12px',
              fontSize: '0.78rem',
              fontWeight: 500,
              cursor: 'pointer',
              transition: 'all 0.15s ease'
            }}
          >
            {preset}
          </button>
        ))}
      </div>
    </div>
  );
}
