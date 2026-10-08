import React, { useState, useEffect, useSyncExternalStore } from 'react';
import { AlertTriangle, RefreshCw } from 'lucide-react';
import Sidebar from './components/Sidebar';
import Topbar from './components/Topbar';
import { subscribeApiStatus, getApiStatus, checkApiHealth } from './api/client';

import LoginScreen from './views/LoginScreen';
import DashboardScreen from './views/DashboardScreen';
import AskScreen from './views/AskScreen';
import AnswerScreen from './views/AnswerScreen';
import GitHubAnalyticsScreen from './views/GitHubAnalyticsScreen';
import GmailIntelligenceScreen from './views/GmailIntelligenceScreen';
import ProjectDetailsScreen from './views/ProjectDetailsScreen';
import MCPConnectionsScreen from './views/MCPConnectionsScreen';
import EvidenceExplorerScreen from './views/EvidenceExplorerScreen';
import ReportsScreen from './views/ReportsScreen';
import WorkflowsScreen from './views/WorkflowsScreen';
import EvaluationDashboardScreen from './views/EvaluationDashboardScreen';
import SettingsScreen from './views/SettingsScreen';

export default function App() {
  // Sync state with URL hash
  const getInitialRoute = () => {
    const hash = window.location.hash.replace('#', '');
    const validRoutes = [
      'login', 'dashboard', 'ask', 'answer', 'github', 'gmail', 
      'project-details', 'mcp', 'evidence', 'reports', 'workflows', 
      'evaluation', 'settings'
    ];
    return validRoutes.includes(hash) ? hash : 'dashboard';
  };

  const [currentRoute, setCurrentRoute] = useState(getInitialRoute);
  const [queryResult, setQueryResult] = useState(null);
  const apiStatus = useSyncExternalStore(subscribeApiStatus, getApiStatus, getApiStatus);

  useEffect(() => {
    checkApiHealth();
  }, []);

  useEffect(() => {
    const handleHashChange = () => {
      const hash = window.location.hash.replace('#', '');
      if (hash) {
        setCurrentRoute(hash);
      }
    };
    window.addEventListener('hashchange', handleHashChange);
    return () => window.removeEventListener('hashchange', handleHashChange);
  }, []);

  const navigateTo = (routeId) => {
    setCurrentRoute(routeId);
    window.location.hash = routeId;
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  // Render LoginScreen directly as full page
  if (currentRoute === 'login') {
    return <LoginScreen navigateTo={navigateTo} />;
  }

  return (
    <div style={{ display: 'flex', minHeight: '100vh', background: 'var(--bg-main)' }}>
      {/* Sidebar Navigation */}
      <Sidebar currentRoute={currentRoute} navigateTo={navigateTo} />

      {/* Main Content Area */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0 }}>
        {/* Visible API failure banner: a dead backend must never look like an empty static UI */}
        {!apiStatus.reachable && (
          <div className="alert-box alert-red" style={{ margin: '12px 24px 0' }}>
            <AlertTriangle size={18} color="#DC2626" style={{ flexShrink: 0 }} />
            <div>
              <strong style={{ display: 'block', marginBottom: '2px', color: '#991B1B' }}>
                Backend not reachable at http://localhost:8000
              </strong>
              <span style={{ fontSize: '0.775rem' }}>
                {apiStatus.error} on {apiStatus.endpoint} — start the full stack with{' '}
                <code>start-dev.bat</code>, then{' '}
                <button
                  onClick={() => checkApiHealth()}
                  className="btn btn-secondary btn-sm"
                  style={{ padding: '2px 10px', fontSize: '0.7rem' }}
                >
                  <RefreshCw size={11} /> Retry
                </button>
              </span>
            </div>
          </div>
        )}

        {/* Topbar Navigation */}
        <Topbar navigateTo={navigateTo} />

        {/* View Component Container */}
        <main style={{ flex: 1, padding: '24px 32px 60px 32px', maxWidth: '1440px', width: '100%', margin: '0 auto' }}>
          {currentRoute === 'dashboard' && <DashboardScreen navigateTo={navigateTo} />}
          {currentRoute === 'ask' && <AskScreen navigateTo={navigateTo} setQueryResult={setQueryResult} />}
          {currentRoute === 'answer' && <AnswerScreen navigateTo={navigateTo} queryResult={queryResult} />}
          {currentRoute === 'github' && <GitHubAnalyticsScreen navigateTo={navigateTo} />}
          {currentRoute === 'gmail' && <GmailIntelligenceScreen navigateTo={navigateTo} />}
          {currentRoute === 'project-details' && <ProjectDetailsScreen navigateTo={navigateTo} />}
          {currentRoute === 'mcp' && <MCPConnectionsScreen navigateTo={navigateTo} />}
          {currentRoute === 'evidence' && <EvidenceExplorerScreen navigateTo={navigateTo} />}
          {currentRoute === 'reports' && <ReportsScreen navigateTo={navigateTo} />}
          {currentRoute === 'workflows' && <WorkflowsScreen navigateTo={navigateTo} setQueryResult={setQueryResult} />}
          {currentRoute === 'evaluation' && <EvaluationDashboardScreen navigateTo={navigateTo} />}
          {currentRoute === 'settings' && <SettingsScreen navigateTo={navigateTo} />}
        </main>
      </div>
    </div>
  );
}
