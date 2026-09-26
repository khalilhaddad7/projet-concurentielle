import { useState, useRef, useEffect } from 'react';
import { chatWithRag } from '../services/api';

function Chatbot() {
  const [query, setQuery] = useState('');
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(false);
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [history, loading]);

  const handleSend = async (e) => {
    e.preventDefault();
    if (!query.trim() || loading) return;

    const userMsg = query.trim();
    setQuery('');
    setLoading(true);

    setHistory(prev => [...prev, { type: 'user', text: userMsg }]);

    try {
      const res = await chatWithRag(userMsg, 5);
      const data = res.data;

      setHistory(prev => [...prev, {
        type: 'bot',
        text: data.answer,
        sources: data.sources || [],
        success: data.success,
      }]);
    } catch (err) {
      setHistory(prev => [...prev, {
        type: 'bot',
        text: `❌ Impossible de contacter le backend. Vérifie que le serveur FastAPI tourne sur ${import.meta.env.VITE_API_URL || 'http://127.0.0.1:8001'}.`,
        sources: [],
        success: false,
      }]);
    } finally {
      setLoading(false);
    }
  };

  const suggestions = [
    "Quel partenariat Stripe et OpenAI ont-ils lancé ?",
    "Quels problèmes de sécurité concernent Hugging Face ?",
    "Quel est le nombre d'utilisateurs de ChatGPT ?",
    "Quelles sont les dernières actualités d'Anthropic ?",
  ];

  return (
    <div style={{
      maxWidth: '900px',
      margin: '0 auto',
      height: 'calc(100vh - 64px)',
      display: 'flex',
      flexDirection: 'column',
    }}>
      {/* Header */}
      <div style={{
        padding: '1.5rem 2rem',
        borderBottom: '1px solid #334155',
      }}>
        <h1 style={{ fontSize: '1.5rem', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <span style={{ fontSize: '1.75rem' }}>🤖</span>
          Assistant de veille stratégique
        </h1>
        <p style={{ color: '#94a3b8', fontSize: '0.9rem', marginTop: '0.25rem' }}>
          Pose une question sur vos articles. Le chatbot répond uniquement à partir de vos données indexées.
        </p>
      </div>

      {/* Messages */}
      <div style={{
        flex: 1,
        overflowY: 'auto',
        padding: '1.5rem 2rem',
        display: 'flex',
        flexDirection: 'column',
        gap: '1.25rem',
      }}>
        {history.length === 0 && (
          <div style={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            height: '100%',
            gap: '1rem',
            color: '#64748b',
          }}>
            <div style={{ fontSize: '4rem' }}>💬</div>
            <p style={{ fontSize: '1.1rem' }}>Commencez une conversation</p>
            <div style={{
              display: 'flex',
              flexWrap: 'wrap',
              gap: '0.75rem',
              justifyContent: 'center',
              maxWidth: '600px',
              marginTop: '0.5rem',
            }}>
              {suggestions.map((s, i) => (
                <button
                  key={i}
                  onClick={() => { setQuery(s); }}
                  style={{
                    padding: '0.6rem 1rem',
                    background: 'rgba(56, 189, 248, 0.1)',
                    border: '1px solid rgba(56, 189, 248, 0.2)',
                    borderRadius: '20px',
                    color: '#38bdf8',
                    cursor: 'pointer',
                    fontSize: '0.85rem',
                    transition: 'all 0.2s',
                  }}
                  onMouseEnter={e => {
                    e.currentTarget.style.background = 'rgba(56, 189, 248, 0.2)';
                  }}
                  onMouseLeave={e => {
                    e.currentTarget.style.background = 'rgba(56, 189, 248, 0.1)';
                  }}
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        {history.map((msg, i) => (
          <div key={i} style={{
            display: 'flex',
            justifyContent: msg.type === 'user' ? 'flex-end' : 'flex-start',
            animation: 'fadeIn 0.3s ease-out',
          }}>
            <div style={{
              maxWidth: '85%',
              padding: '1rem 1.25rem',
              borderRadius: msg.type === 'user' ? '16px 16px 4px 16px' : '16px 16px 16px 4px',
              background: msg.type === 'user'
                ? 'linear-gradient(135deg, #38bdf8, #0284c7)'
                : '#1e293b',
              color: msg.type === 'user' ? 'white' : '#e2e8f0',
              border: msg.type === 'user' ? 'none' : '1px solid #334155',
              boxShadow: '0 4px 12px rgba(0,0,0,0.15)',
              lineHeight: 1.6,
            }}>
              <div style={{
                fontSize: '0.75rem',
                fontWeight: 600,
                marginBottom: '0.5rem',
                opacity: 0.7,
                display: 'flex',
                alignItems: 'center',
                gap: '0.4rem',
              }}>
                {msg.type === 'user' ? '👤 Vous' : '🤖 Assistant'}
              </div>
              <div style={{ whiteSpace: 'pre-wrap', fontSize: '0.95rem' }}>
                {msg.text}
              </div>

              {msg.sources && msg.sources.length > 0 && (
                <div style={{
                  marginTop: '1rem',
                  paddingTop: '1rem',
                  borderTop: '1px solid #334155',
                }}>
                  <div style={{
                    fontSize: '0.75rem',
                    fontWeight: 600,
                    color: '#94a3b8',
                    marginBottom: '0.5rem',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '0.4rem',
                  }}>
                    📚 Sources utilisées
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
                    {msg.sources.map((s, j) => (
                      <a
                        key={j}
                        href={s.url}
                        target="_blank"
                        rel="noreferrer"
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: '0.5rem',
                          padding: '0.5rem 0.75rem',
                          background: '#0f172a',
                          borderRadius: '8px',
                          color: '#38bdf8',
                          textDecoration: 'none',
                          fontSize: '0.85rem',
                          border: '1px solid #334155',
                          transition: 'all 0.2s',
                        }}
                        onMouseEnter={e => {
                          e.currentTarget.style.borderColor = '#38bdf8';
                        }}
                        onMouseLeave={e => {
                          e.currentTarget.style.borderColor = '#334155';
                        }}
                      >
                        <span style={{
                          width: '8px',
                          height: '8px',
                          borderRadius: '50%',
                          background: s.category === 'Produit' ? '#38bdf8' :
                                     s.category === 'Finance' ? '#22c55e' :
                                     s.category === 'Stratégie' ? '#a78bfa' : '#64748b',
                          flexShrink: 0,
                        }} />
                        <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                          {s.title}
                        </span>
                        <span style={{ marginLeft: 'auto', color: '#64748b', fontSize: '0.75rem', whiteSpace: 'nowrap' }}>
                          {s.category}
                        </span>
                      </a>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        ))}

        {loading && (
          <div style={{ display: 'flex', gap: '0.5rem', padding: '1rem' }}>
            <span style={{
              width: '8px',
              height: '8px',
              background: '#38bdf8',
              borderRadius: '50%',
              animation: 'pulse 1.4s ease-in-out 0s infinite',
            }} />
            <span style={{
              width: '8px',
              height: '8px',
              background: '#38bdf8',
              borderRadius: '50%',
              animation: 'pulse 1.4s ease-in-out 0.2s infinite',
            }} />
            <span style={{
              width: '8px',
              height: '8px',
              background: '#38bdf8',
              borderRadius: '50%',
              animation: 'pulse 1.4s ease-in-out 0.4s infinite',
            }} />
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div style={{
        padding: '1.25rem 2rem',
        borderTop: '1px solid #334155',
        background: '#0f172a',
      }}>
        <form onSubmit={handleSend} style={{ display: 'flex', gap: '0.75rem', maxWidth: '900px', margin: '0 auto' }}>
          <input
            type="text"
            value={query}
            onChange={e => setQuery(e.target.value)}
            placeholder="Posez votre question sur vos articles..."
            style={{
              flex: 1,
              padding: '0.9rem 1.25rem',
              background: '#1e293b',
              border: '1px solid #334155',
              borderRadius: '12px',
              color: '#f1f5f9',
              fontSize: '0.95rem',
              outline: 'none',
              transition: 'all 0.2s',
            }}
            onFocus={e => {
              e.target.style.borderColor = '#38bdf8';
              e.target.style.boxShadow = '0 0 0 3px rgba(56, 189, 248, 0.1)';
            }}
            onBlur={e => {
              e.target.style.borderColor = '#334155';
              e.target.style.boxShadow = 'none';
            }}
          />
          <button
            type="submit"
            disabled={loading || !query.trim()}
            style={{
              padding: '0.9rem 1.5rem',
              background: loading ? '#334155' : 'linear-gradient(135deg, #38bdf8, #0284c7)',
              color: 'white',
              border: 'none',
              borderRadius: '12px',
              cursor: loading ? 'not-allowed' : 'pointer',
              fontWeight: 600,
              fontSize: '0.95rem',
              transition: 'all 0.2s',
              display: 'flex',
              alignItems: 'center',
              gap: '0.5rem',
            }}
          >
            {loading ? '⏳' : '➤'} {loading ? 'Envoi...' : 'Envoyer'}
          </button>
        </form>
      </div>
    </div>
  );
}

export default Chatbot;