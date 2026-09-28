import { createContext, useContext, useEffect, useState, useCallback } from 'react';
import {
  loginUser,
  registerUser,
  fetchMe,
  setAccessToken,
  setRefreshToken,
  getRefreshToken,
  setOnAuthFailure,
} from '../services/api';

const AuthContext = createContext(null);

// Hook pratique pour consommer le contexte d'auth partout dans l'app.
// eslint-disable-next-line react-refresh/only-export-components
export const useAuth = () => useContext(AuthContext);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  // loading = vrai pendant la tentative de restauration de session au démarrage,
  // pour éviter un "flash" vers /login avant d'avoir vérifié le refresh token.
  const [loading, setLoading] = useState(true);

  const logout = useCallback(() => {
    setAccessToken(null);
    setRefreshToken(null);
    setUser(null);
  }, []);

  // Au montage : on branche le callback de déconnexion forcée (appelé par
  // l'intercepteur Axios si le refresh échoue) puis on tente de restaurer la
  // session à partir du refresh token présent en localStorage.
  useEffect(() => {
    setOnAuthFailure(() => setUser(null));

    const restoreSession = async () => {
      if (!getRefreshToken()) {
        setLoading(false);
        return;
      }
      try {
        // accessToken est nul au démarrage : /auth/me renverra 401, ce qui
        // déclenche automatiquement le refresh via l'intercepteur, puis rejoue
        // la requête avec le nouvel access token.
        const res = await fetchMe();
        setUser(res.data);
      } catch {
        logout();
      } finally {
        setLoading(false);
      }
    };

    restoreSession();
  }, [logout]);

  const login = async (email, password) => {
    const res = await loginUser(email, password);
    setAccessToken(res.data.access_token);
    setRefreshToken(res.data.refresh_token);
    const me = await fetchMe();
    setUser(me.data);
    return me.data;
  };

  const register = async (email, password) => {
    await registerUser(email, password);
    // Connexion automatique juste après l'inscription.
    return login(email, password);
  };

  const value = {
    user,
    loading,
    login,
    register,
    logout,
    isAuthenticated: !!user,
    isAdmin: user?.role === 'admin',
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
