import { useState, useRef, useEffect, useCallback } from 'react';
import {
  sendChat, fetchConversations, fetchConversation, deleteConversation,
  sendMessageFeedback, fetchChatSuggestions,
} from '../services/api';

const CATEGORY_DOT = {
  Produit: '#38bdf8', Finance: '#22c55e', 'Stratégie': '#a78bfa',
  'Ressources Humaines': '#f472b6', 'Non classé': '#64748b',
};

const fmtDate = (iso) => {
  if (!iso) return '';
  const d = new Date(iso);
  return isNaN(d) ? '' : d.toLocaleDateString('fr-FR', { day: '2-digit', month: 'short' });
};

function Chatbot() {
  const [conversations, setConversations] = useState([]);
  const [currentConvId, setCurrentConvId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [suggestions, setSuggestions] = useState([]);
  const messagesEndRef = useRef(null);

  const loadConversations = useCallback(() => {
    fetchConversations().then(r => setConversations(r.data)).catch(() => {});
  }, []);

  useEffect(() => {
    loadConversations();
    fetchChatSuggestions().then(r => setSuggestions(r.data.suggestions || [])).catch(() => setSuggestions([]));
  }, [loadConversations]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading]);

  const startNewConversation = () => {
    setCurrentConvId(null);
    setMessages([]);
    setQuery('');
  };

  const openConversation = async (id) => {
    try {
      const res = await fetchConversation(id);
      setCurrentConvId(id);
      setMessages(res.data.messages || []);
    } catch { /* ignore */ }
  };

  const handleDelete = async (id, e) => {
    e.stopPropagation();
    if (!window.confirm('Supprimer cette conversation et tous ses messages ?')) return;
    try {
      await deleteConversation(id);
      if (id === currentConvId) startNewConversation();
      loadConversations();
    } catch { /* ignore */ }
  };

  const send = async (text) => {
    const q = (text !== undefined ? text : query).trim();
    if (!q || loading) return;
    setQuery('');
    setLoading(true);
    setMessages(prev => [...prev, { role: 'user', content: q }]);
    try {
      const res = await sendChat(q, currentConvId);
      const d = res.data;
      setCurrentConvId(d.conversation_id);
      setMessages(prev => [...prev, {
        id: d.assistant_message_id, role: 'assistant',
        content: d.answer, sources: d.sources || [], feedback: null,
      }]);
      loadConversations(); // met à jour titre + ordre
    } catch {
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: '❌ Impossible de contacter le backend. Vérifiez que le serveur FastAPI tourne.',
        sources: [], feedback: null,
      }]);
    } finally {
      setLoading(false);
    }
  };

  const handleFeedback = async (index, msgId, value) => {
    if (!msgId) return;
    try {
      const res = await sendMessageFeedback(msgId, value);
      setMessages(prev => prev.map((m, i) => (i === index ? { ...m, feedback: res.data.feedback } : m)));
    } catch { /* ignore */ }
  };

  return (
    <div style={{ display: 'flex', height: 'calc(100vh - 64px)' }}>
      {/* ─── Sidebar ─── */}
      <aside style={{
        width: '280px', flexShrink: 0, background: '#0f172a', borderRight: '1px solid #334155',
        display: 'flex', flexDirection: 'column',
      }}>
        <div style={{ padding: '1rem' }}>
          <button
            onClick={startNewConversation}
            style={{
              width: '100%', padding: '0.7rem', borderRadius: '10px', cursor: 'pointer',
              background: 'linear-gradient(135deg, #38bdf8, #0284c7)', color: 'white',
              border: 'none', fontWeight: 600, fontSize: '0.9rem',
            }}
          >
            ＋ Nouvelle conversation
          </button>
        </div>
        <div style={{ flex: 1, overflowY: 'auto', padding: '0 0.5rem 1rem' }}>
          {conversations.length === 0 && (
            <p style={{ color: '#64748b', fontSize: '0.85rem', textAlign: 'center', marginTop: '1rem' }}>
              Aucune conversation
            </p>
          )}
          {conversations.map(c => {
            const active = c.id === currentConvId;
            return (
              <div
                key={c.id}
                onClick={() => openConversation(c.id)}
                style={{
                  display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '0.5rem',
                  padding: '0.6rem 0.75rem', margin: '0.25rem 0', borderRadius: '8px', cursor: 'pointer',
                  background: active ? 'rgba(56, 189, 248, 0.12)' : 'transparent',
                  border: `1px solid ${active ? 'rgba(56, 189, 248, 0.3)' : 'transparent'}`,
                }}
                onMouseEnter={e => { if (!active) e.currentTarget.style.background = '#1e293b'; }}
                onMouseLeave={e => { if (!active) e.currentTarget.style.background = 'transparent'; }}
              >
                <div style={{ overflow: 'hidden' }}>
                  <div style={{
                    color: active ? '#38bdf8' : '#e2e8f0', fontSize: '0.85rem', fontWeight: 500,
                    overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                  }}>
                    {c.title}
                  </div>
                  <div style={{ color: '#64748b', fontSize: '0.72rem' }}>{fmtDate(c.updated_at || c.created_at)}</div>
                </div>
                <button
                  onClick={(e) => handleDelete(c.id, e)}
                  title="Supprimer"
                  style={{
                    flexShrink: 0, background: 'transparent', border: 'none', cursor: 'pointer',
                    color: '#64748b', fontSize: '1rem', padding: '0.2rem',
                  }}
                  onMouseEnter={e => (e.currentTarget.style.color = '#ef4444')}
                  onMouseLeave={e => (e.currentTarget.style.color = '#64748b')}
                >
                  🗑️
                </button>
              </div>
            );
          })}
        </div>
      </aside>

      {/* ─── Zone de chat principale ─── */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0 }}>
        <div style={{ padding: '1.25rem 2rem', borderBottom: '1px solid #334155' }}>
          <h1 style={{ fontSize: '1.35rem', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
            <span style={{ fontSize: '1.6rem' }}>🤖</span> Assistant de veille stratégique
          </h1>
          <p style={{ color: '#94a3b8', fontSize: '0.85rem', marginTop: '0.2rem' }}>
            Réponses fondées uniquement sur vos articles indexés. Le contexte de la conversation est conservé.
          </p>
        </div>

        <div style={{ flex: 1, overflowY: 'auto', padding: '1.5rem 2rem', display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
          {messages.length === 0 && (
            <div style={{
              display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
              height: '100%', gap: '1rem', color: '#64748b',
            }}>
              <div style={{ fontSize: '3.5rem' }}>💬</div>
              <p style={{ fontSize: '1.05rem' }}>Posez une question pour démarrer</p>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.6rem', justifyContent: 'center', maxWidth: '640px', marginTop: '0.5rem' }}>
                {suggestions.map((s, i) => (
                  <button
                    key={i}
                    onClick={() => setQuery(s)}
                    style={{
                      padding: '0.55rem 0.9rem', background: 'rgba(56, 189, 248, 0.1)',
                      border: '1px solid rgba(56, 189, 248, 0.25)', borderRadius: '20px',
                      color: '#38bdf8', cursor: 'pointer', fontSize: '0.82rem',
                    }}
                    onMouseEnter={e => (e.currentTarget.style.background = 'rgba(56, 189, 248, 0.2)')}
                    onMouseLeave={e => (e.currentTarget.style.background = 'rgba(56, 189, 248, 0.1)')}
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map((msg, i) => (
            <div key={msg.id ?? `tmp-${i}`} style={{ display: 'flex', justifyContent: msg.role === 'user' ? 'flex-end' : 'flex-start' }}>
              <div style={{
                maxWidth: '85%', padding: '1rem 1.25rem',
                borderRadius: msg.role === 'user' ? '16px 16px 4px 16px' : '16px 16px 16px 4px',
                background: msg.role === 'user' ? 'linear-gradient(135deg, #38bdf8, #0284c7)' : '#1e293b',
                color: msg.role === 'user' ? 'white' : '#e2e8f0',
                border: msg.role === 'user' ? 'none' : '1px solid #334155',
                boxShadow: '0 4px 12px rgba(0,0,0,0.15)', lineHeight: 1.6,
              }}>
                <div style={{ fontSize: '0.72rem', fontWeight: 600, marginBottom: '0.4rem', opacity: 0.7 }}>
                  {msg.role === 'user' ? '👤 Vous' : '🤖 Assistant'}
                </div>
                <div style={{ whiteSpace: 'pre-wrap', fontSize: '0.95rem' }}>{msg.content}</div>

                {/* Sources */}
                {msg.sources && msg.sources.length > 0 && (
                  <div style={{ marginTop: '1rem', paddingTop: '0.85rem', borderTop: '1px solid #334155' }}>
                    <div style={{ fontSize: '0.72rem', fontWeight: 600, color: '#94a3b8', marginBottom: '0.5rem' }}>
                      📚 Sources utilisées
                    </div>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
                      {msg.sources.map((s, j) => (
                        <a key={j} href={s.url} target="_blank" rel="noreferrer" style={{
                          display: 'flex', alignItems: 'center', gap: '0.5rem', padding: '0.5rem 0.75rem',
                          background: '#0f172a', borderRadius: '8px', color: '#38bdf8', textDecoration: 'none',
                          fontSize: '0.82rem', border: '1px solid #334155',
                        }}>
                          <span style={{ width: 8, height: 8, borderRadius: '50%', background: CATEGORY_DOT[s.category] || '#64748b', flexShrink: 0 }} />
                          <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{s.title}</span>
                          <span style={{ marginLeft: 'auto', color: '#64748b', fontSize: '0.72rem', whiteSpace: 'nowrap' }}>{s.category}</span>
                        </a>
                      ))}
                    </div>
                  </div>
                )}

                {/* Feedback 👍/👎 (réponses de l'assistant ayant un id) */}
                {msg.role === 'assistant' && msg.id && (
                  <div style={{ marginTop: '0.85rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <span style={{ fontSize: '0.72rem', color: '#64748b' }}>Cette réponse vous a-t-elle aidé ?</span>
                    <FeedbackButton active={msg.feedback === 'positif'} onClick={() => handleFeedback(i, msg.id, 'positif')} label="👍" activeColor="#22c55e" />
                    <FeedbackButton active={msg.feedback === 'negatif'} onClick={() => handleFeedback(i, msg.id, 'negatif')} label="👎" activeColor="#ef4444" />
                  </div>
                )}
              </div>
            </div>
          ))}

          {loading && (
            <div style={{ display: 'flex', gap: '0.5rem', padding: '0.5rem' }}>
              {[0, 0.2, 0.4].map((d, i) => (
                <span key={i} style={{ width: 8, height: 8, background: '#38bdf8', borderRadius: '50%', animation: `pulse 1.4s ease-in-out ${d}s infinite` }} />
              ))}
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Saisie */}
        <div style={{ padding: '1.1rem 2rem', borderTop: '1px solid #334155', background: '#0f172a' }}>
          <form
            onSubmit={(e) => { e.preventDefault(); send(); }}
            style={{ display: 'flex', gap: '0.75rem' }}
          >
            <input
              type="text"
              value={query}
              onChange={e => setQuery(e.target.value)}
              placeholder="Posez votre question sur vos articles…"
              style={{
                flex: 1, padding: '0.85rem 1.2rem', background: '#1e293b', border: '1px solid #334155',
                borderRadius: '12px', color: '#f1f5f9', fontSize: '0.95rem', outline: 'none',
              }}
              onFocus={e => (e.target.style.borderColor = '#38bdf8')}
              onBlur={e => (e.target.style.borderColor = '#334155')}
            />
            <button
              type="submit"
              disabled={loading || !query.trim()}
              style={{
                padding: '0.85rem 1.5rem',
                background: loading ? '#334155' : 'linear-gradient(135deg, #38bdf8, #0284c7)',
                color: 'white', border: 'none', borderRadius: '12px',
                cursor: loading || !query.trim() ? 'not-allowed' : 'pointer', fontWeight: 600, fontSize: '0.95rem',
              }}
            >
              {loading ? '⏳' : '➤'}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}

function FeedbackButton({ active, onClick, label, activeColor }) {
  return (
    <button
      onClick={onClick}
      style={{
        border: `1px solid ${active ? activeColor : '#334155'}`,
        background: active ? `${activeColor}22` : 'transparent',
        borderRadius: '8px', padding: '0.2rem 0.5rem', cursor: 'pointer', fontSize: '0.9rem',
        filter: active ? 'none' : 'grayscale(0.4)', opacity: active ? 1 : 0.75,
      }}
    >
      {label}
    </button>
  );
}

export default Chatbot;
