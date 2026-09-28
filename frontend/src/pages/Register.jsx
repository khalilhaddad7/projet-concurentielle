import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { AuthShell, Field, ErrorBox, SubmitButton } from './Login';

function Register() {
  const { register } = useAuth();
  const navigate = useNavigate();

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');

    if (password.length < 8) {
      setError('Le mot de passe doit contenir au moins 8 caractères.');
      return;
    }
    if (password !== confirm) {
      setError('Les mots de passe ne correspondent pas.');
      return;
    }

    setLoading(true);
    try {
      await register(email, password);
      // Connexion automatique effectuée dans register() -> on va au dashboard.
      navigate('/', { replace: true });
    } catch (err) {
      const detail = err.response?.data?.detail;
      if (Array.isArray(detail)) {
        // Erreur de validation Pydantic (ex: email invalide)
        setError('Email invalide ou données incorrectes.');
      } else {
        setError(typeof detail === 'string' ? detail : "Impossible de créer le compte.");
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <AuthShell title="Créer un compte" subtitle="Inscrivez-vous pour accéder à la veille">
      <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
        <Field label="Email" type="email" value={email} onChange={setEmail} placeholder="vous@exemple.com" />
        <Field label="Mot de passe" type="password" value={password} onChange={setPassword} placeholder="8 caractères minimum" />
        <Field label="Confirmer le mot de passe" type="password" value={confirm} onChange={setConfirm} placeholder="••••••••" />

        {error && <ErrorBox message={error} />}

        <SubmitButton loading={loading} label="Créer mon compte" loadingLabel="Création…" />
      </form>

      <p style={{ marginTop: '1.5rem', textAlign: 'center', color: '#94a3b8', fontSize: '0.9rem' }}>
        Déjà un compte ?{' '}
        <Link to="/login" style={{ color: '#38bdf8', fontWeight: 600 }}>Se connecter</Link>
      </p>
    </AuthShell>
  );
}

export default Register;
