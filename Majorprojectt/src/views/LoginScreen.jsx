import React, { useState } from 'react';
import { Mail, Lock, Shield, ArrowRight, Building2, Eye, EyeOff } from 'lucide-react';
import { KnowledgeOpsLogo, GitHubIcon, GmailIcon } from '../components/Icons';

export default function LoginScreen({ navigateTo }) {
  const [email, setEmail] = useState('alex.shah@acme.com');
  const [password, setPassword] = useState('••••••••••••');
  const [remember, setRemember] = useState(true);
  const [showPass, setShowPass] = useState(false);

  const handleSignIn = (e) => {
    e.preventDefault();
    navigateTo('dashboard');
  };

  return (
    <div style={{
      minHeight: '100vh',
      background: '#F8FAFC',
      display: 'flex',
      flexDirection: 'column',
      fontFamily: 'var(--font-main)'
    }}>
      {/* Top Bar */}
      <header style={{
        height: '64px',
        padding: '0 40px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        background: '#FFFFFF',
        borderBottom: '1px solid #E2E8F0'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <KnowledgeOpsLogo size={28} />
          <span style={{ fontWeight: 800, fontSize: '1.1rem', color: '#0F172A' }}>KnowledgeOps AI</span>
        </div>
        <div style={{ fontSize: '0.825rem', color: '#64748B' }}>
          Enterprise knowledge. Connected.
        </div>
      </header>

      {/* Main Container */}
      <div style={{
        flex: 1,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '40px 20px'
      }}>
        <div style={{
          maxWidth: '1080px',
          width: '100%',
          display: 'grid',
          gridTemplateColumns: '1fr 440px',
          gap: '40px',
          alignItems: 'center'
        }}>
          {/* Left Column: Hero & Callout */}
          <div>
            <div className="badge badge-purple" style={{ marginBottom: '16px', fontSize: '0.75rem', letterSpacing: '0.5px' }}>
              PROJECT INTELLIGENCE, WITH EVIDENCE
            </div>
            
            <h1 style={{
              fontSize: '2.4rem',
              fontWeight: 800,
              color: '#0F172A',
              lineHeight: 1.25,
              letterSpacing: '-0.5px',
              marginBottom: '16px'
            }}>
              Transforming Fragmented Enterprise Knowledge into Intelligent Project Decisions
            </h1>

            <p style={{ fontSize: '1rem', color: '#475569', marginBottom: '24px', lineHeight: 1.6 }}>
              Bring GitHub activity and Gmail conversations together. Ask one question. Get an answer your team can trace.
            </p>

            {/* Source Cards */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px', marginBottom: '24px' }}>
              <div style={{ padding: '14px 16px', background: '#FFFFFF', border: '1px solid #E2E8F0', borderRadius: '8px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontWeight: 700, color: '#0F172A', fontSize: '0.9rem' }}>
                  <GitHubIcon size={20} />
                  <span>GitHub</span>
                </div>
                <div style={{ fontSize: '0.775rem', color: '#64748B', marginTop: '4px' }}>
                  Code, issues & pull requests
                </div>
              </div>

              <div style={{ padding: '14px 16px', background: '#FFFFFF', border: '1px solid #E2E8F0', borderRadius: '8px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontWeight: 700, color: '#0F172A', fontSize: '0.9rem' }}>
                  <GmailIcon size={20} />
                  <span>Gmail</span>
                </div>
                <div style={{ fontSize: '0.775rem', color: '#64748B', marginTop: '4px' }}>
                  Conversations & decisions
                </div>
              </div>
            </div>

            <div style={{ textAlign: 'center', margin: '12px 0 20px 0' }}>
              <span className="badge badge-purple" style={{ fontSize: '0.7rem' }}>
                MCP + RAG + MULTI-AGENT REASONING
              </span>
            </div>

            {/* Feature Callout Box */}
            <div style={{
              background: '#EEF2FF',
              border: '1px solid #C7D2FE',
              borderRadius: '10px',
              padding: '20px',
              marginBottom: '20px'
            }}>
              <div style={{ display: 'flex', gap: '8px', marginBottom: '8px' }}>
                <span className="badge badge-purple" style={{ fontSize: '0.7rem' }}>Evidence-backed</span>
                <span style={{ fontSize: '0.75rem', color: '#475569', fontWeight: 500 }}>Platform API · v2.4</span>
              </div>
              <div style={{ fontWeight: 700, fontSize: '0.95rem', color: '#1E1B4B', marginBottom: '4px' }}>
                A clearer release decision
              </div>
              <div style={{ fontSize: '0.875rem', fontWeight: 600, color: '#312E81', marginBottom: '6px' }}>
                Resolve the auth review before the October 9 release.
              </div>
              <div style={{ fontSize: '0.8rem', color: '#4338CA', marginBottom: '12px' }}>
                Issue #142, PR #284, and the release readiness email all point to the same blocker.
              </div>
              <div style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', fontSize: '0.75rem', color: '#6D28D9', fontWeight: 600, background: '#FFFFFF', padding: '4px 8px', borderRadius: '4px' }}>
                <GmailIcon size={14} /> Source citations included in every answer
              </div>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.8rem', color: '#059669', fontWeight: 500 }}>
              <Shield size={16} />
              <span>Your workspace permissions stay in control.</span>
            </div>
          </div>

          {/* Right Column: Login Card */}
          <div className="card" style={{ padding: '32px 28px', background: '#FFFFFF' }}>
            <h2 style={{ fontSize: '1.4rem', fontWeight: 800, color: '#0F172A', marginBottom: '4px' }}>
              Welcome back
            </h2>
            <p style={{ fontSize: '0.825rem', color: '#64748B', marginBottom: '24px' }}>
              Sign in to your KnowledgeOps AI workspace.
            </p>

            {/* Enterprise SSO Button */}
            <button 
              onClick={() => navigateTo('dashboard')}
              className="btn btn-secondary" 
              style={{ width: '100%', padding: '10px', justifyContent: 'center', marginBottom: '20px', fontSize: '0.85rem' }}
            >
              <Building2 size={16} />
              <span>Continue with enterprise SSO</span>
            </button>

            {/* Divider */}
            <div style={{
              display: 'flex',
              alignItems: 'center',
              margin: '20px 0',
              color: '#94A3B8',
              fontSize: '0.75rem'
            }}>
              <div style={{ flex: 1, height: '1px', background: '#E2E8F0' }}></div>
              <span style={{ padding: '0 12px' }}>or use your email</span>
              <div style={{ flex: 1, height: '1px', background: '#E2E8F0' }}></div>
            </div>

            {/* Login Form */}
            <form onSubmit={handleSignIn}>
              <div style={{ marginBottom: '16px' }}>
                <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 600, color: '#334155', marginBottom: '6px' }}>
                  Email
                </label>
                <div style={{ position: 'relative' }}>
                  <input 
                    type="email" 
                    className="input" 
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    style={{ paddingRight: '36px' }}
                  />
                  <Mail size={16} color="#94A3B8" style={{ position: 'absolute', right: '12px', top: '50%', transform: 'translateY(-50%)' }} />
                </div>
              </div>

              <div style={{ marginBottom: '20px' }}>
                <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 600, color: '#334155', marginBottom: '6px' }}>
                  Password
                </label>
                <div style={{ position: 'relative' }}>
                  <input 
                    type={showPass ? "text" : "password"} 
                    className="input" 
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    style={{ paddingRight: '36px' }}
                  />
                  <div 
                    onClick={() => setShowPass(!showPass)}
                    style={{ position: 'absolute', right: '12px', top: '50%', transform: 'translateY(-50%)', cursor: 'pointer' }}
                  >
                    {showPass ? <EyeOff size={16} color="#94A3B8" /> : <Eye size={16} color="#94A3B8" />}
                  </div>
                </div>
              </div>

              {/* Controls */}
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '24px', fontSize: '0.8rem' }}>
                <label style={{ display: 'flex', alignItems: 'center', gap: '6px', cursor: 'pointer', color: '#475569' }}>
                  <input 
                    type="checkbox" 
                    checked={remember}
                    onChange={(e) => setRemember(e.target.checked)}
                  />
                  <span>Remember me</span>
                </label>
                <a href="#forgot" style={{ color: '#2563EB', textDecoration: 'none', fontWeight: 600 }}>
                  Forgot password?
                </a>
              </div>

              <button 
                type="submit" 
                className="btn btn-primary" 
                style={{ width: '100%', padding: '11px', fontSize: '0.9rem', justifyContent: 'center' }}
              >
                <span>Sign in</span>
                <ArrowRight size={16} />
              </button>
            </form>

            <div style={{ textAlign: 'center', fontSize: '0.75rem', color: '#64748B', marginTop: '20px' }}>
              Need workspace access? Contact your administrator.
            </div>

            <div style={{
              marginTop: '24px',
              paddingTop: '16px',
              borderTop: '1px solid #F1F5F9',
              textAlign: 'center',
              fontSize: '0.7rem',
              color: '#94A3B8',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '6px'
            }}>
              <Shield size={12} color="#94A3B8" />
              <span>Secure sign-in · Encrypted connections · Role-based access</span>
            </div>
          </div>
        </div>
      </div>

      {/* Footer */}
      <footer style={{
        padding: '16px 40px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        fontSize: '0.75rem',
        color: '#94A3B8',
        borderTop: '1px solid #E2E8F0',
        background: '#FFFFFF'
      }}>
        <div>© 2026 KnowledgeOps AI</div>
        <div style={{ display: 'flex', gap: '16px' }}>
          <span>Privacy policy</span>
          <span>·</span>
          <span>Terms of service</span>
          <span>·</span>
          <span>Help</span>
        </div>
      </footer>
    </div>
  );
}
