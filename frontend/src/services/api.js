import axios from 'axios';

// URL de base de l'API, définie UNE SEULE FOIS via la variable d'environnement
// VITE_API_URL (voir frontend/.env). Valeur de repli si la variable est absente.
// Le backend tourne sur le port 8001 sur cette machine (port 8000 bloqué par Windows).
const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8001';

// ─────────────────────────────────────────────────────────────────────
// Stockage des tokens
// ─────────────────────────────────────────────────────────────────────
// ACCESS TOKEN : gardé UNIQUEMENT en mémoire (variable de module + state React
// dans AuthContext). Il n'est jamais écrit dans localStorage : ainsi, même en
// cas de faille XSS, il n'est pas persistant et disparaît au rechargement.
let accessToken = null;
export const setAccessToken = (token) => { accessToken = token; };
export const getAccessToken = () => accessToken;

// REFRESH TOKEN : stocké dans localStorage.
// ⚠️ RISQUE XSS ASSUMÉ : localStorage est lisible par n'importe quel JavaScript
// s'exécutant sur la page. Un attaquant qui parvient à injecter du script (XSS)
// pourrait donc voler ce refresh token. Le choix plus sûr serait un cookie
// httpOnly (inaccessible au JS), mais il impose en cross-origin (front :5173 /
// back :8001) des cookies SameSite=None; Secure, donc HTTPS — impraticable dans
// ce setup de dev en HTTP. On documente ici ce compromis (voir les explications
// fournies avec cette fonctionnalité). En production : préférer le cookie httpOnly
// derrière HTTPS ou un reverse-proxy same-origin.
const REFRESH_TOKEN_KEY = 'veille_refresh_token';
export const getRefreshToken = () => {
  try { return localStorage.getItem(REFRESH_TOKEN_KEY); }
  catch { return null; }
};
export const setRefreshToken = (token) => {
  try {
    if (token) localStorage.setItem(REFRESH_TOKEN_KEY, token);
    else localStorage.removeItem(REFRESH_TOKEN_KEY);
  } catch { /* localStorage indisponible (mode privé) : on ignore silencieusement */ }
};

// Callback appelé quand le refresh échoue définitivement (déconnexion forcée).
// Défini par AuthContext pour vider l'état utilisateur et rediriger vers /login.
let onAuthFailure = () => {};
export const setOnAuthFailure = (fn) => { onAuthFailure = fn; };

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// ─── Intercepteur de requête : ajoute automatiquement le Bearer token ──
api.interceptors.request.use((config) => {
  if (accessToken) {
    config.headers.Authorization = `Bearer ${accessToken}`;
  }
  return config;
});

// ─── Intercepteur de réponse : refresh automatique sur 401 ─────────────
// Si une requête renvoie 401 (access token expiré), on tente UNE fois de
// renouveler l'access token via /auth/refresh, puis on rejoue la requête.
// Les requêtes concurrentes pendant un refresh sont mises en file d'attente.
let isRefreshing = false;
let pendingQueue = [];

const flushQueue = (error, token = null) => {
  pendingQueue.forEach(({ resolve, reject }) => (error ? reject(error) : resolve(token)));
  pendingQueue = [];
};

const isAuthEndpoint = (url = '') =>
  url.includes('/auth/login') || url.includes('/auth/refresh') || url.includes('/auth/register');

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const original = error.config;
    const status = error.response?.status;

    // On ne tente un refresh que sur un 401, hors routes d'auth, et une seule fois.
    if (status === 401 && original && !original._retry && !isAuthEndpoint(original.url)) {
      const refresh = getRefreshToken();
      if (!refresh) {
        onAuthFailure();
        return Promise.reject(error);
      }

      // Un refresh est déjà en cours : on met la requête en attente.
      if (isRefreshing) {
        return new Promise((resolve, reject) => {
          pendingQueue.push({ resolve, reject });
        }).then((token) => {
          original._retry = true;
          original.headers.Authorization = `Bearer ${token}`;
          return api(original);
        });
      }

      original._retry = true;
      isRefreshing = true;
      try {
        // Appel "brut" (sans intercepteur) pour éviter toute boucle de refresh.
        const resp = await axios.post(`${API_BASE_URL}/auth/refresh`, { refresh_token: refresh });
        const newToken = resp.data.access_token;
        setAccessToken(newToken);
        flushQueue(null, newToken);
        original.headers.Authorization = `Bearer ${newToken}`;
        return api(original);
      } catch (refreshError) {
        // Refresh token lui-même invalide/expiré : déconnexion.
        flushQueue(refreshError, null);
        setAccessToken(null);
        setRefreshToken(null);
        onAuthFailure();
        return Promise.reject(refreshError);
      } finally {
        isRefreshing = false;
      }
    }

    return Promise.reject(error);
  }
);

// ─── Endpoints d'authentification ──────────────────────────────────────
export const registerUser = (email, password) =>
  api.post('/auth/register', { email, password });

export const loginUser = (email, password) =>
  api.post('/auth/login', { email, password });

export const fetchMe = () => api.get('/auth/me');

// ─── Endpoints métier (inchangés, le token est ajouté automatiquement) ──
export const fetchArticles = (skip = 0, limit = 1000) =>
  api.get(`/articles?skip=${skip}&limit=${limit}`);

export const collectArticles = (daysBack = 7) =>
  api.post(`/collect?days_back=${daysBack}`);

export const processNlp = (limit = 20) =>
  api.post(`/process-nlp?limit=${limit}`);

export const indexArticles = (limit = null) => {
  const queryString = limit ? `?limit=${limit}` : '';
  return api.post(`/index-articles${queryString}`);
};

// ─── Chatbot conversationnel ────────────────────────────────────────
export const sendChat = (query, conversationId = null, nResults = 5) =>
  api.post('/chat', { query, conversation_id: conversationId, n_results: nResults });

export const fetchConversations = () => api.get('/conversations');
export const fetchConversation = (id) => api.get(`/conversations/${id}`);
export const deleteConversation = (id) => api.delete(`/conversations/${id}`);
export const sendMessageFeedback = (messageId, feedback) =>
  api.post(`/messages/${messageId}/feedback`, { feedback });
export const fetchChatSuggestions = () => api.get('/chat/suggestions');

// ─── Exports (téléchargements protégés par JWT → responseType blob) ──────
export const exportArticles = (format, filters = {}) => {
  const params = { format };
  ['competitor', 'category', 'sentiment', 'date_from', 'date_to'].forEach(k => {
    if (filters[k]) params[k] = filters[k];
  });
  return api.get('/export/articles', { params, responseType: 'blob' });
};

export const exportCompetitorReport = (competitor) =>
  api.get(`/export/report/${encodeURIComponent(competitor)}`, { params: { format: 'pdf' }, responseType: 'blob' });

export const exportWeeklyReport = () =>
  api.get('/export/weekly-report', { params: { format: 'pdf' }, responseType: 'blob' });

// ─── Statistiques (Dashboard) ───────────────────────────────────────────
export const fetchTimeline = (competitor = null, period = 30) => {
  const params = new URLSearchParams({ period: String(period) });
  if (competitor) params.set('competitor', competitor);
  return api.get(`/stats/timeline?${params.toString()}`);
};

export const fetchComparison = () => api.get('/stats/comparison');

export const fetchCriticalTimeline = (limit = 50) =>
  api.get(`/stats/critical-timeline?limit=${limit}`);

export default api;
