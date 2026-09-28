import { useEffect, useState, useCallback } from 'react';
import {
  LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from 'recharts';
import { fetchArticles, fetchTimeline, fetchComparison, fetchCriticalTimeline, exportCompetitorReport, exportWeeklyReport } from '../services/api';
import { saveBlob } from '../utils/download';

// Concurrents suivis (valeurs = exactement celles renvoyées par l'API).
const COMPETITORS = ['Mistral AI', 'Hugging Face', 'OpenAI', 'Anthropic', 'Google DeepMind'];

const COMPETITOR_COLORS = {
  'Mistral AI': '#38bdf8',
  'Hugging Face': '#f472b6',
  'OpenAI': '#22c55e',
  'Anthropic': '#a78bfa',
  'Google DeepMind': '#f59e0b',
};

const CATEGORY_ORDER = ['Produit', 'Finance', 'Ressources Humaines', 'Stratégie', 'Non classé'];
const CATEGORY_COLORS = {
  'Produit': '#38bdf8',
  'Finance': '#22c55e',
  'Ressources Humaines': '#f472b6',
  'Stratégie': '#a78bfa',
  'Non classé': '#64748b',
};

const PANEL = {
  background: '#1e293b',
  borderRadius: '16px',
  padding: '1.5rem',
  border: '1px solid #334155',
};

const AXIS_TICK = { fill: '#94a3b8', fontSize: 12 };
const TOOLTIP_STYLE = {
  contentStyle: { background: '#0f172a', border: '1px solid #334155', borderRadius: '8px', color: '#e2e8f0' },
  labelStyle: { color: '#94a3b8' },
};

const fmtDate = (iso) => {
  if (!iso) return '—';
  const d = new Date(iso);
  return isNaN(d) ? iso : d.toLocaleDateString('fr-FR', { day: '2-digit', month: 'short' });
};

function Dashboard() {
  const [period, setPeriod] = useState(30);
  const [lineData, setLineData] = useState([]);
  const [loadingLine, setLoadingLine] = useState(true);
  const [comparison, setComparison] = useState([]);
  const [critical, setCritical] = useState([]);
  const [summary, setSummary] = useState({ total: 0, processed: 0 });
  const [recent, setRecent] = useState([]);

  // Données chargées une seule fois (indépendantes de la période).
  useEffect(() => {
    fetchComparison().then(r => setComparison(r.data)).catch(() => setComparison([]));
    fetchCriticalTimeline().then(r => setCritical(r.data)).catch(() => setCritical([]));
    fetchArticles(0, 1000).then(r => {
      const arts = r.data || [];
      setSummary({ total: arts.length, processed: arts.filter(a => a.is_processed).length });
      setRecent(arts.slice(-5).reverse());
    }).catch(() => {});
  }, []);

  // Rechargement RÉEL depuis le serveur à chaque changement de période
  // (une requête agrégée par concurrent, puis fusion par date pour le multi-lignes).
  const loadTimelines = useCallback(async (p) => {
    setLoadingLine(true);
    try {
      const results = await Promise.all(
        COMPETITORS.map(c =>
          fetchTimeline(c, p).then(r => ({ c, data: r.data })).catch(() => ({ c, data: [] }))
        )
      );
      const byDate = {};
      results.forEach(({ c, data }) => {
        (data || []).forEach(pt => {
          if (!byDate[pt.date]) byDate[pt.date] = { date: pt.date };
          byDate[pt.date][c] = pt.sentiment_moyen;
        });
      });
      setLineData(Object.values(byDate).sort((a, b) => a.date.localeCompare(b.date)));
    } finally {
      setLoadingLine(false);
    }
  }, []);

  // Rechargement volontaire des données serveur quand la période change.
  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => { loadTimelines(period); }, [period, loadTimelines]);

  // Données du BarChart (volume par concurrent, empilé par catégorie).
  const barData = comparison.map(row => {
    const entry = { competitor: row.competitor };
    CATEGORY_ORDER.forEach(cat => { entry[cat] = row.alerts?.[cat] || 0; });
    return entry;
  });

  // Export de rapports PDF (protégés par JWT → blob). `exportingKey` = concurrent ou 'weekly'.
  const [exportingKey, setExportingKey] = useState(null);
  const [exportError, setExportError] = useState('');

  const downloadReport = async (key, promiseFactory, filename) => {
    setExportError('');
    setExportingKey(key);
    try {
      const res = await promiseFactory();
      saveBlob(res, filename);
    } catch {
      setExportError('Échec de la génération du rapport PDF. Réessayez.');
    } finally {
      setExportingKey(null);
    }
  };

  return (
    <div style={{ maxWidth: '1400px', margin: '0 auto', padding: '2rem' }}>
      <div className="animate-fade-in" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '2rem', gap: '1rem', flexWrap: 'wrap' }}>
        <div>
          <h1 style={{ fontSize: '2rem', fontWeight: 700, marginBottom: '0.5rem' }}>Tableau de bord</h1>
          <p style={{ color: '#94a3b8' }}>Vue d'ensemble de votre veille concurrentielle</p>
        </div>
        <button
          onClick={() => downloadReport('weekly', exportWeeklyReport, 'rapport_hebdomadaire.pdf')}
          disabled={exportingKey === 'weekly'}
          style={{
            display: 'flex', alignItems: 'center', gap: '0.5rem', padding: '0.6rem 1.2rem',
            background: 'rgba(239, 68, 68, 0.1)', color: '#ef4444', border: '1px solid rgba(239, 68, 68, 0.3)',
            borderRadius: '10px', cursor: exportingKey === 'weekly' ? 'wait' : 'pointer', fontWeight: 600, fontSize: '0.9rem',
          }}
        >
          {exportingKey === 'weekly' ? '⏳ Génération…' : '📄 Rapport hebdomadaire'}
        </button>
      </div>

      {exportError && (
        <div style={{
          padding: '0.85rem 1.25rem', borderRadius: '10px', marginBottom: '1.5rem',
          background: 'rgba(239, 68, 68, 0.1)', border: '1px solid rgba(239, 68, 68, 0.3)', color: '#ef4444', fontWeight: 500,
        }}>
          {exportError}
        </div>
      )}

      {/* Cartes de synthèse */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(230px, 1fr))', gap: '1.5rem', marginBottom: '1.5rem' }}>
        <StatCard title="Articles collectés" value={summary.total} icon="📰" gradient="linear-gradient(135deg, #38bdf8, #0284c7)" />
        <StatCard title="Traités (NLP)" value={summary.processed} icon="🧠" gradient="linear-gradient(135deg, #22c55e, #16a34a)" />
        <StatCard title="À traiter" value={summary.total - summary.processed} icon="⏳" gradient="linear-gradient(135deg, #f59e0b, #d97706)" />
        <StatCard title="Événements critiques" value={critical.length} icon="🚨" gradient="linear-gradient(135deg, #ef4444, #b91c1c)" />
      </div>

      {/* 1. Évolution du sentiment par concurrent + sélecteur de période */}
      <div style={{ ...PANEL, marginBottom: '1.5rem' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem', marginBottom: '1.25rem' }}>
          <h3 style={{ fontSize: '1.1rem', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            📈 Sentiment moyen par concurrent
          </h3>
          <div style={{ display: 'flex', gap: '0.5rem' }}>
            {[7, 30, 90].map(p => (
              <button
                key={p}
                onClick={() => setPeriod(p)}
                style={{
                  padding: '0.4rem 0.9rem',
                  borderRadius: '8px',
                  fontSize: '0.85rem',
                  fontWeight: 600,
                  cursor: 'pointer',
                  background: period === p ? 'rgba(56, 189, 248, 0.15)' : 'transparent',
                  color: period === p ? '#38bdf8' : '#94a3b8',
                  border: `1px solid ${period === p ? 'rgba(56, 189, 248, 0.4)' : '#334155'}`,
                }}
              >
                {p} j
              </button>
            ))}
          </div>
        </div>

        {loadingLine ? (
          <EmptyBox text="Chargement des données…" />
        ) : lineData.length === 0 ? (
          <EmptyBox text="Aucune donnée sur cette période." />
        ) : (
          <div style={{ width: '100%', height: 320 }}>
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={lineData} margin={{ top: 5, right: 20, bottom: 5, left: -10 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                <XAxis dataKey="date" tick={AXIS_TICK} tickFormatter={fmtDate} stroke="#334155" />
                <YAxis domain={[-1, 1]} tick={AXIS_TICK} stroke="#334155" />
                <Tooltip {...TOOLTIP_STYLE} labelFormatter={fmtDate} />
                <Legend wrapperStyle={{ fontSize: 12 }} />
                {COMPETITORS.map(c => (
                  <Line
                    key={c}
                    type="monotone"
                    dataKey={c}
                    stroke={COMPETITOR_COLORS[c]}
                    strokeWidth={2}
                    dot={false}
                    connectNulls={false}
                  />
                ))}
              </LineChart>
            </ResponsiveContainer>
          </div>
        )}
        <p style={{ color: '#64748b', fontSize: '0.8rem', marginTop: '0.75rem' }}>
          Indice de −1 (négatif) à +1 (positif){period > 60 ? ' · agrégation hebdomadaire' : ' · agrégation quotidienne'}.
        </p>
      </div>

      {/* 2. Volume d'articles par concurrent, empilé par catégorie */}
      <div style={{ ...PANEL, marginBottom: '1.5rem' }}>
        <h3 style={{ fontSize: '1.1rem', fontWeight: 600, marginBottom: '1.25rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          📊 Volume d'articles par concurrent (par catégorie)
        </h3>
        {barData.length === 0 ? (
          <EmptyBox text="Aucune donnée disponible." />
        ) : (
          <div style={{ width: '100%', height: 320 }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={barData} margin={{ top: 5, right: 20, bottom: 5, left: -10 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                <XAxis dataKey="competitor" tick={AXIS_TICK} stroke="#334155" />
                <YAxis tick={AXIS_TICK} stroke="#334155" allowDecimals={false} />
                <Tooltip {...TOOLTIP_STYLE} cursor={{ fill: 'rgba(255,255,255,0.04)' }} />
                <Legend wrapperStyle={{ fontSize: 12 }} />
                {CATEGORY_ORDER.map(cat => (
                  <Bar key={cat} dataKey={cat} stackId="a" fill={CATEGORY_COLORS[cat]} />
                ))}
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>

      {/* 3. Scorecard comparatif */}
      <div style={{ ...PANEL, marginBottom: '1.5rem' }}>
        <h3 style={{ fontSize: '1.1rem', fontWeight: 600, marginBottom: '1.25rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          🏆 Scorecard comparatif
        </h3>
        {comparison.length === 0 ? (
          <EmptyBox text="Aucune donnée disponible." />
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'separate', borderSpacing: '0 0.5rem' }}>
              <thead>
                <tr>
                  <Th>Concurrent</Th>
                  <Th align="right">Articles</Th>
                  <Th align="center">Sentiment moyen</Th>
                  <Th align="right">Dernière actualité</Th>
                  <Th align="center">Rapport</Th>
                </tr>
              </thead>
              <tbody>
                {comparison.map(row => {
                  const s = sentimentStyle(row.sentiment_moyen);
                  return (
                    <tr key={row.competitor} style={{ background: s.bg }}>
                      <Td>
                        <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem', fontWeight: 600, color: '#e2e8f0' }}>
                          <span style={{ width: 10, height: 10, borderRadius: '50%', background: COMPETITOR_COLORS[row.competitor] || '#64748b' }} />
                          {row.competitor}
                        </span>
                      </Td>
                      <Td align="right"><span style={{ fontWeight: 700, color: '#e2e8f0' }}>{row.total_articles}</span></Td>
                      <Td align="center">
                        <span style={{ color: s.color, fontWeight: 700 }}>{s.label}</span>
                      </Td>
                      <Td align="right"><span style={{ color: '#94a3b8', fontSize: '0.85rem' }}>{fmtDate(row.last_article_date)}</span></Td>
                      <Td align="center">
                        <button
                          onClick={() => downloadReport(
                            row.competitor,
                            () => exportCompetitorReport(row.competitor),
                            `rapport_${row.competitor.replace(/\s+/g, '_')}.pdf`,
                          )}
                          disabled={exportingKey === row.competitor}
                          style={{
                            padding: '0.4rem 0.8rem', borderRadius: '8px', fontSize: '0.8rem', fontWeight: 600,
                            cursor: exportingKey === row.competitor ? 'wait' : 'pointer',
                            background: 'rgba(56, 189, 248, 0.1)', color: '#38bdf8', border: '1px solid rgba(56, 189, 248, 0.3)',
                            whiteSpace: 'nowrap',
                          }}
                        >
                          {exportingKey === row.competitor ? '⏳' : '📄 PDF'}
                        </button>
                      </Td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* 4. Frise chronologique des événements critiques */}
      <div style={{ ...PANEL, marginBottom: '1.5rem' }}>
        <h3 style={{ fontSize: '1.1rem', fontWeight: 600, marginBottom: '1.25rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          🚨 Événements c
          ritiques
        </h3>
        {critical.length === 0 ? (
          <EmptyBox text="Aucun événement critique détecté." />
        ) : (
          <div style={{ overflowX: 'auto', paddingBottom: '0.5rem' }}>
            <div style={{ display: 'flex', alignItems: 'stretch', gap: '1rem', position: 'relative', minWidth: 'min-content' }}>
              {/* ligne horizontale de la frise */}
              <div style={{ position: 'absolute', top: 6, left: 0, right: 0, height: 2, background: '#334155' }} />
              {critical.map(ev => (
                <a
                  key={ev.id}
                  href={ev.url}
                  target="_blank"
                  rel="noreferrer"
                  title={ev.title}
                  style={{
                    position: 'relative',
                    flex: '0 0 220px',
                    textDecoration: 'none',
                    paddingTop: '1.25rem',
                  }}
                >
                  <span style={{
                    position: 'absolute', top: 0, left: 8, width: 14, height: 14, borderRadius: '50%',
                    background: CATEGORY_COLORS[ev.category] || '#ef4444', border: '2px solid #0f172a',
                  }} />
                  <div style={{
                    background: '#0f172a', border: '1px solid #334155', borderRadius: '10px', padding: '0.75rem',
                    transition: 'border-color 0.2s', height: '100%',
                  }}
                    onMouseEnter={e => (e.currentTarget.style.borderColor = '#38bdf8')}
                    onMouseLeave={e => (e.currentTarget.style.borderColor = '#334155')}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.4rem' }}>
                      <span style={{ color: '#64748b', fontSize: '0.75rem' }}>{fmtDate(ev.date)}</span>
                      <span style={{
                        fontSize: '0.7rem', fontWeight: 600, color: CATEGORY_COLORS[ev.category] || '#ef4444',
                        background: 'rgba(255,255,255,0.05)', padding: '0.1rem 0.5rem', borderRadius: '6px',
                      }}>
                        {ev.category || '—'}
                      </span>
                    </div>
                    <div style={{ color: '#e2e8f0', fontSize: '0.85rem', fontWeight: 600, lineHeight: 1.35,
                      display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}>
                      {ev.title}
                    </div>
                    <div style={{ color: '#94a3b8', fontSize: '0.75rem', marginTop: '0.4rem' }}>{ev.competitor}</div>
                  </div>
                </a>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Articles récents */}
      <div style={PANEL}>
        <h3 style={{ fontSize: '1.1rem', fontWeight: 600, marginBottom: '1rem' }}>🕐 Articles récents</h3>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
          {recent.map(a => (
            <div key={a.id} style={{
              display: 'flex', alignItems: 'center', justifyContent: 'space-between',
              padding: '0.75rem 1rem', background: '#0f172a', borderRadius: '10px', border: '1px solid #334155',
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', overflow: 'hidden' }}>
                <span style={{
                  background: CATEGORY_COLORS[a.alert_category] || '#64748b', color: 'white',
                  padding: '0.2rem 0.6rem', borderRadius: '6px', fontSize: '0.75rem', fontWeight: 600, whiteSpace: 'nowrap',
                }}>
                  {a.alert_category}
                </span>
                <span style={{ color: '#e2e8f0', fontSize: '0.95rem', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {a.title}
                </span>
              </div>
              <span style={{ color: '#64748b', fontSize: '0.85rem', whiteSpace: 'nowrap' }}>{a.competitor}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// Renvoie le style (fond/couleur/label) selon la polarité du sentiment moyen.
function sentimentStyle(s) {
  if (s == null) return { bg: 'rgba(100,116,139,0.10)', color: '#94a3b8', label: '—' };
  if (s > 0.1) return { bg: 'rgba(34,197,94,0.10)', color: '#22c55e', label: `Positif (${s.toFixed(2)})` };
  if (s < -0.1) return { bg: 'rgba(239,68,68,0.10)', color: '#ef4444', label: `Négatif (${s.toFixed(2)})` };
  return { bg: 'rgba(148,163,184,0.10)', color: '#94a3b8', label: `Neutre (${s.toFixed(2)})` };
}

function EmptyBox({ text }) {
  return (
    <div style={{ textAlign: 'center', padding: '3rem 1rem', color: '#64748b', fontSize: '0.95rem' }}>
      {text}
    </div>
  );
}

function Th({ children, align = 'left' }) {
  return (
    <th style={{ textAlign: align, padding: '0.5rem 1rem', fontSize: '0.75rem', fontWeight: 600, color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
      {children}
    </th>
  );
}

function Td({ children, align = 'left' }) {
  return <td style={{ textAlign: align, padding: '0.85rem 1rem' }}>{children}</td>;
}

function StatCard({ title, value, icon, gradient }) {
  return (
    <div style={{ ...PANEL, position: 'relative', overflow: 'hidden' }}>
      <div style={{
        position: 'absolute', top: 0, right: 0, width: '100px', height: '100px',
        background: gradient, opacity: 0.1, borderRadius: '50%', transform: 'translate(30%, -30%)',
      }} />
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '0.75rem' }}>
        <span style={{ fontSize: '1.5rem' }}>{icon}</span>
        <span style={{ color: '#94a3b8', fontSize: '0.9rem', fontWeight: 500 }}>{title}</span>
      </div>
      <div style={{ fontSize: '2.5rem', fontWeight: 700, background: gradient, WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
        {value}
      </div>
    </div>
  );
}

export default Dashboard;
