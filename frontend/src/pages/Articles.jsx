import { useEffect, useState } from 'react';
import { fetchArticles, collectArticles, processNlp, indexArticles, exportArticles } from '../services/api';
import { saveBlob } from '../utils/download';
import { useAuth } from '../context/AuthContext';

const COMPETITORS = ['Mistral AI', 'Hugging Face', 'OpenAI', 'Anthropic', 'Google DeepMind'];
const CATEGORIES = ['Produit', 'Finance', 'Ressources Humaines', 'Stratégie', 'Non classé'];
const SENTIMENTS = ['Positif', 'Neutre', 'Négatif'];

function Articles() {
  const { isAdmin } = useAuth();
  const [articles, setArticles] = useState([]);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState('');
  const [messageType, setMessageType] = useState('info');
  const [filters, setFilters] = useState({ competitor: '', category: '', sentiment: '' });
  const [exportOpen, setExportOpen] = useState(false);
  const [exporting, setExporting] = useState(false);

  const load = () => {
    setLoading(true);
    fetchArticles().then(res => {
      setArticles(res.data);
      setLoading(false);
    });
  };

  useEffect(() => { load(); }, []);

  const showMessage = (text, type = 'info') => {
    setMessage(text);
    setMessageType(type);
    setTimeout(() => setMessage(''), 5000);
  };

  const handleCollect = async () => {
    showMessage('⏳ Collecte en cours...', 'info');
    try {
      const res = await collectArticles(7);
      showMessage(`✅ ${res.data.inserted} articles collectés`, 'success');
      load();
    } catch (err) {
      showMessage('❌ Erreur lors de la collecte', 'error');
    }
  };

  const handleProcess = async () => {
    showMessage('⏳ Traitement NLP en cours (peut prendre plusieurs minutes)...', 'info');
    try {
      const res = await processNlp(10);
      showMessage(`✅ ${res.data.processed} traités, ${res.data.errors} erreurs`, 'success');
      load();
    } catch (err) {
      showMessage('❌ Erreur NLP', 'error');
    }
  };

  const handleIndex = async () => {
    showMessage('⏳ Indexation ChromaDB...', 'info');
    try {
      const res = await indexArticles();
      showMessage(`✅ ${res.data.indexed} articles indexés`, 'success');
    } catch (err) {
      showMessage('❌ Erreur d\'indexation', 'error');
    }
  };

  // Filtrage client-side (les mêmes filtres sont envoyés à l'export côté serveur).
  const visibleArticles = articles.filter(a =>
    (!filters.competitor || a.competitor === filters.competitor) &&
    (!filters.category || a.alert_category === filters.category) &&
    (!filters.sentiment || a.sentiment === filters.sentiment)
  );

  const handleExport = async (format) => {
    setExportOpen(false);
    setExporting(true);
    showMessage('⏳ Génération de l\'export…', 'info');
    try {
      const res = await exportArticles(format, filters);
      saveBlob(res, `articles.${format}`);
      showMessage('✅ Export téléchargé', 'success');
    } catch {
      showMessage('❌ Erreur lors de l\'export', 'error');
    } finally {
      setExporting(false);
    }
  };

  const categoryColors = {
    'Produit': { bg: 'rgba(56, 189, 248, 0.15)', text: '#38bdf8', border: 'rgba(56, 189, 248, 0.3)' },
    'Finance': { bg: 'rgba(34, 197, 94, 0.15)', text: '#22c55e', border: 'rgba(34, 197, 94, 0.3)' },
    'Stratégie': { bg: 'rgba(167, 139, 250, 0.15)', text: '#a78bfa', border: 'rgba(167, 139, 250, 0.3)' },
    'Ressources Humaines': { bg: 'rgba(244, 114, 182, 0.15)', text: '#f472b6', border: 'rgba(244, 114, 182, 0.3)' },
    'Non classé': { bg: 'rgba(100, 116, 139, 0.15)', text: '#94a3b8', border: 'rgba(100, 116, 139, 0.3)' },
  };

  const sentimentColors = {
    'Positif': '#22c55e',
    'Négatif': '#ef4444',
    'Neutre': '#94a3b8',
    'Inconnu': '#64748b',
  };

  return (
    <div style={{ maxWidth: '1400px', margin: '0 auto', padding: '2rem' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '2rem' }}>
        <div>
          <h1 style={{ fontSize: '2rem', fontWeight: 700 }}>📰 Articles collectés</h1>
          <p style={{ color: '#94a3b8', marginTop: '0.25rem' }}>
            {visibleArticles.length} article{visibleArticles.length > 1 ? 's' : ''}
            {visibleArticles.length !== articles.length ? ` (sur ${articles.length})` : ' dans la base'}
          </p>
        </div>
        <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center' }}>
          {/* Actions d'administration : visibles uniquement pour les admins.
              Le backend les protège aussi (require_admin) — ce masquage est
              purement cosmétique côté client. */}
          {isAdmin && (
            <>
              <ActionButton onClick={handleCollect} icon="🔄" label="Collecter" color="#38bdf8" />
              <ActionButton onClick={handleProcess} icon="🧠" label="NLP" color="#22c55e" />
              <ActionButton onClick={handleIndex} icon="📦" label="Indexer" color="#a78bfa" />
            </>
          )}

          {/* Menu d'export (applique les filtres courants) */}
          <div style={{ position: 'relative' }}>
            <ActionButton
              onClick={() => setExportOpen(o => !o)}
              icon={exporting ? '⏳' : '⬇️'}
              label={exporting ? 'Export…' : 'Exporter'}
              color="#f59e0b"
            />
            {exportOpen && !exporting && (
              <div style={{
                position: 'absolute', right: 0, top: 'calc(100% + 0.4rem)', zIndex: 20,
                background: '#1e293b', border: '1px solid #334155', borderRadius: '10px',
                overflow: 'hidden', minWidth: '150px', boxShadow: '0 8px 20px rgba(0,0,0,0.35)',
              }}>
                <ExportItem onClick={() => handleExport('csv')} label="📄 CSV (Excel)" />
                <ExportItem onClick={() => handleExport('xlsx')} label="📊 Excel (.xlsx)" />
              </div>
            )}
          </div>

          <ActionButton onClick={load} icon="🔄" label="Rafraîchir" color="#64748b" />
        </div>
      </div>

      {/* Barre de filtres */}
      <div style={{ display: 'flex', gap: '0.75rem', marginBottom: '1.5rem', flexWrap: 'wrap' }}>
        <FilterSelect value={filters.competitor} onChange={v => setFilters(f => ({ ...f, competitor: v }))}
                      placeholder="Tous les concurrents" options={COMPETITORS} />
        <FilterSelect value={filters.category} onChange={v => setFilters(f => ({ ...f, category: v }))}
                      placeholder="Toutes les catégories" options={CATEGORIES} />
        <FilterSelect value={filters.sentiment} onChange={v => setFilters(f => ({ ...f, sentiment: v }))}
                      placeholder="Tous les sentiments" options={SENTIMENTS} />
        {(filters.competitor || filters.category || filters.sentiment) && (
          <button
            onClick={() => setFilters({ competitor: '', category: '', sentiment: '' })}
            style={{
              padding: '0.55rem 1rem', background: 'transparent', color: '#94a3b8',
              border: '1px solid #334155', borderRadius: '8px', cursor: 'pointer', fontSize: '0.85rem',
            }}
          >
            ✕ Réinitialiser
          </button>
        )}
      </div>

      {message && (
        <div style={{
          padding: '1rem 1.5rem',
          borderRadius: '12px',
          marginBottom: '1.5rem',
          background: messageType === 'success' ? 'rgba(34, 197, 94, 0.1)' :
                     messageType === 'error' ? 'rgba(239, 68, 68, 0.1)' :
                     'rgba(56, 189, 248, 0.1)',
          border: `1px solid ${messageType === 'success' ? 'rgba(34, 197, 94, 0.3)' :
                               messageType === 'error' ? 'rgba(239, 68, 68, 0.3)' :
                               'rgba(56, 189, 248, 0.3)'}`,
          color: messageType === 'success' ? '#22c55e' :
                 messageType === 'error' ? '#ef4444' :
                 '#38bdf8',
          fontWeight: 500,
        }}>
          {message}
        </div>
      )}

      {loading ? (
        <div style={{ textAlign: 'center', padding: '4rem', color: '#64748b' }}>
          <div className="animate-pulse-slow" style={{ fontSize: '3rem', marginBottom: '1rem' }}>⏳</div>
          Chargement des articles...
        </div>
      ) : (
        <div style={{
          background: '#1e293b',
          borderRadius: '16px',
          border: '1px solid #334155',
          overflow: 'hidden',
        }}>
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ background: '#0f172a', borderBottom: '1px solid #334155' }}>
                  <Th>Titre</Th>
                  <Th>Compétiteur</Th>
                  <Th>Catégorie</Th>
                  <Th>Sentiment</Th>
                  <Th>Résumé</Th>
                  <Th>Actions</Th>
                </tr>
              </thead>
              <tbody>
                {visibleArticles.map((a, i) => {
                  const catStyle = categoryColors[a.alert_category] || categoryColors['Non classé'];
                  return (
                    <tr key={a.id} style={{
                      borderBottom: '1px solid #334155',
                      transition: 'background 0.2s',
                    }}
                    onMouseEnter={e => e.currentTarget.style.background = '#252f47'}
                    onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
                    >
                      <Td>
                        <div style={{ fontWeight: 600, color: '#e2e8f0', maxWidth: '350px' }}>
                          {a.title}
                        </div>
                        <div style={{ fontSize: '0.8rem', color: '#64748b', marginTop: '0.25rem' }}>
                          {new Date(a.published_at).toLocaleDateString('fr-FR') || 'Date inconnue'}
                        </div>
                      </Td>
                      <Td>{a.competitor}</Td>
                      <Td>
                        <span style={{
                          background: catStyle.bg,
                          color: catStyle.text,
                          border: `1px solid ${catStyle.border}`,
                          padding: '0.3rem 0.8rem',
                          borderRadius: '20px',
                          fontSize: '0.8rem',
                          fontWeight: 600,
                        }}>
                          {a.alert_category}
                        </span>
                      </Td>
                      <Td>
                        <span style={{ color: sentimentColors[a.sentiment] || '#64748b', fontWeight: 600 }}>
                          {a.sentiment || '—'}
                        </span>
                      </Td>
                      <Td>
                        <div style={{ maxWidth: '300px', color: '#94a3b8', fontSize: '0.9rem', lineHeight: 1.5 }}>
                          {a.summary ? a.summary.substring(0, 120) + '...' : 'Pas de résumé'}
                        </div>
                      </Td>
                      <Td>
                        <a href={a.url} target="_blank" rel="noreferrer" style={{
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: '0.4rem',
                          padding: '0.5rem 1rem',
                          background: 'rgba(56, 189, 248, 0.1)',
                          color: '#38bdf8',
                          borderRadius: '8px',
                          textDecoration: 'none',
                          fontSize: '0.85rem',
                          fontWeight: 500,
                          border: '1px solid rgba(56, 189, 248, 0.2)',
                          transition: 'all 0.2s',
                        }}
                        onMouseEnter={e => {
                          e.currentTarget.style.background = 'rgba(56, 189, 248, 0.2)';
                        }}
                        onMouseLeave={e => {
                          e.currentTarget.style.background = 'rgba(56, 189, 248, 0.1)';
                        }}
                        >
                          🔗 Voir
                        </a>
                      </Td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

function FilterSelect({ value, onChange, placeholder, options }) {
  return (
    <select
      value={value}
      onChange={e => onChange(e.target.value)}
      style={{
        padding: '0.55rem 0.9rem', background: '#1e293b', color: value ? '#e2e8f0' : '#94a3b8',
        border: `1px solid ${value ? 'rgba(56, 189, 248, 0.4)' : '#334155'}`, borderRadius: '8px',
        fontSize: '0.85rem', cursor: 'pointer', outline: 'none',
      }}
    >
      <option value="">{placeholder}</option>
      {options.map(o => <option key={o} value={o}>{o}</option>)}
    </select>
  );
}

function ExportItem({ onClick, label }) {
  return (
    <button
      onClick={onClick}
      style={{
        display: 'block', width: '100%', textAlign: 'left', padding: '0.65rem 1rem',
        background: 'transparent', color: '#e2e8f0', border: 'none', cursor: 'pointer', fontSize: '0.88rem',
      }}
      onMouseEnter={e => (e.currentTarget.style.background = '#334155')}
      onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
    >
      {label}
    </button>
  );
}

function ActionButton({ onClick, icon, label, color }) {
  return (
    <button onClick={onClick} style={{
      display: 'flex',
      alignItems: 'center',
      gap: '0.5rem',
      padding: '0.6rem 1.2rem',
      background: 'rgba(255,255,255,0.05)',
      color: color,
      border: `1px solid ${color}33`,
      borderRadius: '10px',
      cursor: 'pointer',
      fontWeight: 600,
      fontSize: '0.9rem',
      transition: 'all 0.2s',
    }}
    onMouseEnter={e => {
      e.currentTarget.style.background = `${color}22`;
      e.currentTarget.style.transform = 'translateY(-2px)';
    }}
    onMouseLeave={e => {
      e.currentTarget.style.background = 'rgba(255,255,255,0.05)';
      e.currentTarget.style.transform = 'translateY(0)';
    }}
    >
      {icon} {label}
    </button>
  );
}

function Th({ children }) {
  return (
    <th style={{
      padding: '1rem 1.25rem',
      textAlign: 'left',
      fontSize: '0.8rem',
      fontWeight: 600,
      color: '#94a3b8',
      textTransform: 'uppercase',
      letterSpacing: '0.05em',
    }}>
      {children}
    </th>
  );
}

function Td({ children }) {
  return (
    <td style={{
      padding: '1rem 1.25rem',
      color: '#cbd5e1',
      fontSize: '0.9rem',
    }}>
      {children}
    </td>
  );
}

export default Articles;