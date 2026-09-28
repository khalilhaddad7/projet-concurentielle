import { useState } from 'react';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const from = location.state?.from?.pathname || '/';

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      await login(email, password);
      navigate(from, { replace: true });
    } catch (err) {
      const detail = err.response?.data?.detail;
      setError(typeof detail === 'string' ? detail : 'Email ou mot de passe incorrect.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <AuthShell title="Connexion" subtitle="Accédez à votre plateforme de veille">
      <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
        <Field label="Email" type="email" value={email} onChange={setEmail} placeholder="vous@exemple.com" />
        <Field label="Mot de passe" type="password" value={password} onChange={setPassword} placeholder="••••••••" />

        {error && <ErrorBox message={error} />}

        <SubmitButton loading={loading} label="Se connecter" loadingLabel="Connexion…" />
      </form>

      <p style={{ marginTop: '1.5rem', textAlign: 'center', color: '#94a3b8', fontSize: '0.9rem' }}>
        Pas encore de compte ?{' '}
        <Link to="/register" style={{ color: '#38bdf8', fontWeight: 600 }}>Créer un compte</Link>
      </p>
    </AuthShell>
  );
}

// ─── Composants partagés (réutilisés par Register) ─────────────────────

export function AuthShell({ title, subtitle, children }) {
  return (
    <div style={{
      minHeight: 'calc(100vh - 64px)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      padding: '2rem',
    }}>
      <div style={{
        width: '100%',
        maxWidth: '420px',
        background: '#1e293b',
        border: '1px solid #334155',
        borderRadius: '16px',
        padding: '2.5rem',
        boxShadow: '0 8px 24px rgba(0,0,0,0.25)',
      }}>
        <h1 style={{ fontSize: '1.6rem', fontWeight: 700, marginBottom: '0.25rem' }}>{title}</h1>
        <p style={{ color: '#94a3b8', fontSize: '0.9rem', marginBottom: '1.75rem' }}>{subtitle}</p>
        {children}
      </div>
    </div>
  );
}

export function Field({ label, type, value, onChange, placeholder }) {
  return (
    <label style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
      <span style={{ fontSize: '0.85rem', fontWeight: 600, color: '#cbd5e1' }}>{label}</span>
      <input
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        required
        style={{
          padding: '0.8rem 1rem',
          background: '#0f172a',
          border: '1px solid #334155',
          borderRadius: '10px',
          color: '#f1f5f9',
          fontSize: '0.95rem',
          outline: 'none',
        }}
        onFocus={(e) => { e.target.style.borderColor = '#38bdf8'; }}
        onBlur={(e) => { e.target.style.borderColor = '#334155'; }}
      />
    </label>
  );
}

export function ErrorBox({ message }) {
  return (
    <div style={{
      padding: '0.75rem 1rem',
      background: 'rgba(239, 68, 68, 0.1)',
      border: '1px solid rgba(239, 68, 68, 0.3)',
      borderRadius: '10px',
      color: '#ef4444',
      fontSize: '0.85rem',
    }}>
      {message}
    </div>
  );
}

export function SubmitButton({ loading, label, loadingLabel }) {
  return (
    <button
      type="submit"
      disabled={loading}
      style={{
        padding: '0.85rem',
        background: loading ? '#334155' : 'linear-gradient(135deg, #38bdf8, #0284c7)',
        color: 'white',
        border: 'none',
        borderRadius: '10px',
        cursor: loading ? 'not-allowed' : 'pointer',
        fontWeight: 700,
        fontSize: '0.95rem',
        marginTop: '0.25rem',
      }}
    >
      {loading ? loadingLabel : label}
    </button>
  );
}

export default Login;
