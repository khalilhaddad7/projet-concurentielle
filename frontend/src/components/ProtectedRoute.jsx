import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

// Enveloppe une page protégée : redirige vers /login si l'utilisateur n'est pas
// authentifié. Pendant la restauration de session (loading), on n'affiche rien
// pour éviter un flash de la page de login.
function ProtectedRoute({ children }) {
  const { isAuthenticated, loading } = useAuth();
  const location = useLocation();

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: '4rem', color: '#64748b' }}>
        Chargement…
      </div>
    );
  }

  if (!isAuthenticated) {
    // state.from : permet de revenir sur la page demandée après connexion.
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  return children;
}

export default ProtectedRoute;
