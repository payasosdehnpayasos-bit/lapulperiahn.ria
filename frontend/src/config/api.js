// Configuración de API para La Pulpería
import axios from 'axios';

// BACKEND URL DINÁMICO
const getBackendURL = () => {
  const hostname = window.location.hostname;
  
  if (hostname === 'lapulperiahn.shop' || hostname === 'www.lapulperiahn.shop') {
    return `https://${hostname}`;
  }
  
  return window.location.origin;
};

export const BACKEND_URL = getBackendURL();
console.log('[API Config] Backend URL:', BACKEND_URL);

// Crear instancia de axios configurada
const api = axios.create({
  baseURL: BACKEND_URL,
  withCredentials: true,
  timeout: 30000
});

// ✅ MEJORA: Interceptor de request con mejor manejo
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('session_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// ✅ MEJORA: Interceptor de response SIN logout agresivo
api.interceptors.response.use(
  (response) => response,
  (error) => {
    const currentPath = window.location.pathname;
    const isPublicPage = currentPath === '/' || 
                        currentPath === '/auth/callback' || 
                        currentPath.startsWith('/p/');

    // Solo manejar errores 401 (no autorizado)
    if (error.response?.status === 401) {
      // NO redirigir si estamos en páginas públicas
      if (isPublicPage) {
        return Promise.reject(error);
      }

      // Verificar si realmente no hay token
      const hasToken = localStorage.getItem('session_token');
      
      if (!hasToken) {
        // Sin token, redirigir al home
        console.log('[API] Sin token, redirigiendo al home');
        localStorage.removeItem('session_token');
        localStorage.removeItem('user_data');
        window.location.href = '/';
      } else {
        // Con token pero 401 - puede ser token expirado o error temporal
        // NO limpiar inmediatamente, dejar que AuthContext lo maneje
        console.log('[API] Error 401 con token presente - dejando que AuthContext maneje');
      }
    }

    // Para otros errores (timeout, 500, etc) NO hacer nada especial
    // Dejar que el código que hizo la llamada los maneje
    return Promise.reject(error);
  }
);

export { api };
export default BACKEND_URL;
