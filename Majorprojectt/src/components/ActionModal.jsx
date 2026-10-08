import React, { useState } from 'react';
import { X, Play, CheckCircle2, AlertCircle } from 'lucide-react';
import { executeWorkflowAction } from '../services/api';

export default function ActionModal({ recommendation, onClose }) {
  const [isExecuting, setIsExecuting] = useState(false);
  const [executedResult, setExecutedResult] = useState(null);
  const [error, setError] = useState(null);

  if (!recommendation) return null;

  const handleExecute = async () => {
    setIsExecuting(true);
    setError(null);
    try {
      const payload = {
        action_type: recommendation.action_type || 'create_jira_ticket',
        title: recommendation.text,
        description: `Triggered from KnowledgeOps AI Intelligence platform. Action Item: ${recommendation.text}`,
        priority: recommendation.priority || 'High',
        assignee: 'unassigned'
      };
      const res = await executeWorkflowAction(payload);
      setExecutedResult(res);
    } catch (err) {
      setError(err.message || 'Execution failed');
    } finally {
      setIsExecuting(false);
    }
  };

  return (
    <div style={{
      position: 'fixed',
      top: 0, left: 0, right: 0, bottom: 0,
      background: 'rgba(0, 0, 0, 0.75)',
      backdropFilter: 'blur(6px)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      zIndex: 2000,
      padding: '20px'
    }}>
      <div className="glass-card" style={{
        width: '100%',
        maxWidth: '520px',
        padding: '24px',
        border: '1px solid var(--border-highlight)'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px' }}>
          <h3 style={{ fontSize: '1.1rem', fontWeight: 700, margin: 0, color: '#F3F4F6' }}>
            Execute Workflow Action
          </h3>
          <button onClick={onClose} style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer' }}>
            <X size={20} />
          </button>
        </div>

        {!executedResult ? (
          <div>
            <div style={{ background: 'var(--bg-input)', padding: '14px', borderRadius: '8px', marginBottom: '16px' }}>
              <span className="badge badge-high" style={{ marginBottom: '6px' }}>
                Action Type: {recommendation.action_type}
              </span>
              <p style={{ fontSize: '0.9rem', color: '#F3F4F6', margin: 0, fontWeight: 600 }}>
                {recommendation.text}
              </p>
            </div>

            <p style={{ fontSize: '0.82rem', color: 'var(--text-muted)', marginBottom: '20px' }}>
              Write actions are kept disabled by default in KnowledgeOps AI until explicitly confirmed. Executing this step will log an audit action to the backend workflow engine.
            </p>

            {error && (
              <div style={{ color: '#F43F5E', fontSize: '0.82rem', marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                <AlertCircle size={14} /> {error}
              </div>
            )}

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px' }}>
              <button onClick={onClose} className="btn-secondary">Cancel</button>
              <button onClick={handleExecute} disabled={isExecuting} className="btn-primary">
                <Play size={15} />
                {isExecuting ? 'Executing...' : 'Confirm & Execute'}
              </button>
            </div>
          </div>
        ) : (
          <div>
            <div style={{ textAlign: 'center', padding: '16px 0' }}>
              <CheckCircle2 size={48} color="#10B981" style={{ marginBottom: '12px' }} />
              <h4 style={{ fontSize: '1rem', color: '#F3F4F6', margin: '0 0 6px 0' }}>
                Workflow Action Executed!
              </h4>
              <p style={{ fontSize: '0.82rem', color: 'var(--text-muted)', margin: 0 }}>
                {executedResult.message}
              </p>
            </div>

            <div style={{ background: 'var(--bg-input)', padding: '12px', borderRadius: '6px', fontSize: '0.78rem', fontFamily: 'var(--font-mono)', color: '#60A5FA', marginBottom: '20px' }}>
              Action Audit ID: #{executedResult.action_id}
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
              <button onClick={onClose} className="btn-primary">Done</button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
