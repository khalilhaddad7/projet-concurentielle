import { useEffect, useState } from 'react';
import { fetchArticles } from '../services/api';

function Dashboard() {
  const [stats, setStats] = useState({ total: 0, processed: 0, categories: {}, sentiments: {} });
  const [recentArticles, setRecentArticles] = useState([]);

  useEffect(() => {
    fetchArticles(0, 1000).then(res => {
      const articles = res.data;
      const processed = articles.filter(a => a.is_processed).length;
      const cats = {};
      const sens = {};
      
      articles.forEach(a => {
        const cat = a.alert_category || 'Non classé';
        cats[cat] = (cats[cat] || 0) + 1;
        const se = a.sentiment || 'Inconnu';
        sens[se] = (sens[se] || 0) + 1;
      });

      setStats({ total: articles.length, processed, categories: cats, sentiments: sens });
      setRecentArticles(articles.slice(-5).reverse());
    });
  }, []);

  const categoryColors = {
    'Produit': '#38bdf8',
    'Finance': '#22c55e',
    'Stratégie': '#a78bfa',
    'Ressources Humaines': '#f472b6',
    'Non classé': '#64748b',
  };

  const sentimentColors = {
    'Positif': '#22c55e',
    'Négatif': '#ef4444',
    'Neutre': '#94a3b8',
    'Inconnu': '#64748b',
  };

  return (
    <div style={{ maxWidth: '1400px', margin: '0 auto', padding: '2rem' }}>
      <div className="animate-fade-in">
        <h1 style={{ fontSize: '2rem', fontWeight: 700, marginBottom: '0.5rem' }}>
          Tableau de bord
        </h1>
        <p style={{ color: '#94a3b8', marginBottom: '2rem' }}>
          Vue d'ensemble de votre veille concurrentielle
        </p>
      </div>

      {/* Stats cards */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))',
        gap: '1.5rem',
        marginBottom: '2rem',
      }}>
        <StatCard
          title="Articles collectés"
          value={stats.total}
          icon="📰"
          gradient="linear-gradient(135deg, #38bdf8, #0284c7)"
        />
        <StatCard
          title="Traités (NLP)"
          value={stats.processed}
          icon="🧠"
          gradient="linear-gradient(135deg, #22c55e, #16a34a)"
        />
        <StatCard
          title="À traiter"
          value={stats.total - stats.processed}
          icon="⏳"
          gradient="linear-gradient(135deg, #f59e0b, #d97706)"
        />
        <StatCard
          title="Taux de traitement"
          value={stats.total ? Math.round((stats.processed / stats.total) * 100) + '%' : '0%'}
          icon="📈"
          gradient="linear-gradient(135deg, #a78bfa, #7c3aed)"
        />
      </div>

      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(400px, 1fr))',
        gap: '1.5rem',
      }}>
        {/* Categories */}
        <div style={{
          background: '#1e293b',
          borderRadius: '16px',
          padding: '1.5rem',
          border: '1px solid #334155',
        }}>
          <h3 style={{ fontSize: '1.1rem', fontWeight: 600, marginBottom: '1.5rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            🏷️ Répartition par catégorie
          </h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
            {Object.entries(stats.categories).map(([cat, count]) => (
              <div key={cat} style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
                <span style={{
                  width: '12px',
                  height: '12px',
                  borderRadius: '50%',
                  background: categoryColors[cat] || '#64748b',
                  flexShrink: 0,
                }} />
                <span style={{ flex: 1, color: '#cbd5e1', fontSize: '0.95rem' }}>{cat}</span>
                <span style={{
                  background: 'rgba(255,255,255,0.05)',
                  padding: '0.25rem 0.75rem',
                  borderRadius: '20px',
                  fontWeight: 600,
                  fontSize: '0.9rem',
                }}>
                  {count}
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* Sentiments */}
        <div style={{
          background: '#1e293b',
          borderRadius: '16px',
          padding: '1.5rem',
          border: '1px solid #334155',
        }}>
          <h3 style={{ fontSize: '1.1rem', fontWeight: 600, marginBottom: '1.5rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            😊 Répartition par sentiment
          </h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
            {Object.entries(stats.sentiments).map(([sen, count]) => (
              <div key={sen} style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
                <span style={{
                  width: '12px',
                  height: '12px',
                  borderRadius: '50%',
                  background: sentimentColors[sen] || '#64748b',
                  flexShrink: 0,
                }} />
                <span style={{ flex: 1, color: '#cbd5e1', fontSize: '0.95rem' }}>{sen}</span>
                <span style={{
                  background: 'rgba(255,255,255,0.05)',
                  padding: '0.25rem 0.75rem',
                  borderRadius: '20px',
                  fontWeight: 600,
                  fontSize: '0.9rem',
                }}>
                  {count}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Recent articles */}
      <div style={{
        background: '#1e293b',
        borderRadius: '16px',
        padding: '1.5rem',
        border: '1px solid #334155',
        marginTop: '1.5rem',
      }}>
        <h3 style={{ fontSize: '1.1rem', fontWeight: 600, marginBottom: '1rem' }}>
          🕐 Articles récents
        </h3>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
          {recentArticles.map(a => (
            <div key={a.id} style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              padding: '0.75rem 1rem',
              background: '#0f172a',
              borderRadius: '10px',
              border: '1px solid #334155',
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', overflow: 'hidden' }}>
                <span style={{
                  background: categoryColors[a.alert_category] || '#64748b',
                  color: 'white',
                  padding: '0.2rem 0.6rem',
                  borderRadius: '6px',
                  fontSize: '0.75rem',
                  fontWeight: 600,
                  whiteSpace: 'nowrap',
                }}>
                  {a.alert_category}
                </span>
                <span style={{ color: '#e2e8f0', fontSize: '0.95rem', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {a.title}
                </span>
              </div>
              <span style={{ color: '#64748b', fontSize: '0.85rem', whiteSpace: 'nowrap' }}>
                {a.competitor}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function StatCard({ title, value, icon, gradient }) {
  return (
    <div style={{
      background: '#1e293b',
      borderRadius: '16px',
      padding: '1.5rem',
      border: '1px solid #334155',
      position: 'relative',
      overflow: 'hidden',
    }}>
      <div style={{
        position: 'absolute',
        top: 0,
        right: 0,
        width: '100px',
        height: '100px',
        background: gradient,
        opacity: 0.1,
        borderRadius: '50%',
        transform: 'translate(30%, -30%)',
      }} />
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '0.75rem' }}>
        <span style={{ fontSize: '1.5rem' }}>{icon}</span>
        <span style={{ color: '#94a3b8', fontSize: '0.9rem', fontWeight: 500 }}>{title}</span>
      </div>
      <div style={{
        fontSize: '2.5rem',
        fontWeight: 700,
        background: gradient,
        WebkitBackgroundClip: 'text',
        WebkitTextFillColor: 'transparent',
      }}>
        {value}
      </div>
    </div>
  );
}

export default Dashboard;