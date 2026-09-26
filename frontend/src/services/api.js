import axios from 'axios';

// URL de base de l'API, définie UNE SEULE FOIS via la variable d'environnement
// VITE_API_URL (voir frontend/.env). Valeur de repli si la variable est absente.
// Le backend tourne sur le port 8001 sur cette machine (port 8000 bloqué par Windows).
const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8001';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

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

export const chatWithRag = (query, nResults = 5) =>
  api.post(`/chat?query=${encodeURIComponent(query)}&n_results=${nResults}`);

export default api;