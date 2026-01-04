import React, { createContext, useContext, useState, useEffect, useCallback, useRef } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { BACKEND_URL } from '../config/api';

const AuthContext = createContext(null);

// Helper para obtener headers con token
const getAuthHeaders = () => {
  const token = localStorage.getItem('session_token');
  return token ? { Authorization: `Bearer ${token}` } : {};
};

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const isLoggingIn = useRef(false);

  // ✅ SOLUCIÓN 1: Cargar usuario desde localStorage PRIMERO
  useEffect(() => {
    const savedUser = localStorage.getItem('user_data');
    if (savedUser) {
      try {
        const userData = JSON.parse(savedUser);
        setUser(userData);
        console.log('[Auth] Usuario cargado desde localStorage:', userData.name);
      } catch (e) {
        console.error('[Auth] Error parsing saved user:', e);
        localStorage.removeItem('user_data');
      }
    }
  }, []);

  // Check existing session on mount
  const checkAuth = useCallback(async () => {
    if (isLoggingIn.current) {
      return null;
    }
    
    const token = localStorage.getItem('session_token');
    
    // Si no hay token, no hay sesión
    if (!token) {
      setUser(null);
      setLoading(false);
      localStorage.removeItem('user_data'); // Limpiar datos guardados
      return null;
    }
    
    try {
      const response = await axios.get(`${BACKEND_URL}/api/auth/me`, {
        timeout: 15000,
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });
      
      // ✅ SOLUCIÓN 2: Guardar usuario en localStorage
      setUser(response.data);
      localStorage.setItem('user_data', JSON.stringify(response.data));
      console.log('[Auth] Sesión verificada y guardada');
      
      return response.data;
    } catch (error) {
      console.log('[Auth] Error verificando sesión:', error.message);
      
      // ✅ SOLUCIÓN 3: Solo limpiar en errores 401 (no autorizado)
      if (error.response?.status === 401) {
        console.log('[Auth] Token inválido (401), limpiando sesión');
        localStorage.removeItem('session_token');
        localStorage.removeItem('user_data');
        setUser(null);
      } else {
        // Para errores de red (timeout, connection refused, etc)
        // MANTENER la sesión actual del usuario
        console.log('[Auth] Error de red, manteniendo sesión actual');
        
        // Si tenemos usuario en localStorage, mantenerlo
        const savedUser = localStorage.getItem('user_data');
        if (savedUser && !user) {
          try {
            const userData = JSON.parse(savedUser);
            setUser(userData);
            console.log('[Auth] Usuario restaurado desde localStorage tras error de red');
          } catch (e) {
            console.error('[Auth] Error restaurando usuario:', e);
          }
        }
      }
      return null;
    } finally {
      setLoading(false);
    }
  }, [user]);

  // Login with session_id from Google OAuth (Emergent Auth)
  const login = useCallback(async (sessionId) => {
    isLoggingIn.current = true;
    try {
      setLoading(true);
      
      const response = await axios.post(
        `${BACKEND_URL}/api/auth/session`,
        { session_id: sessionId },
        { 
          withCredentials: true,
          timeout: 15000,
          headers: {
            'Content-Type': 'application/json'
          }
        }
      );

      // ✅ SOLUCIÓN 4: Guardar token Y usuario
      if (response.data.session_token) {
        localStorage.setItem('session_token', response.data.session_token);
      }
      
      setUser(response.data);
      localStorage.setItem('user_data', JSON.stringify(response.data));
      console.log('[Auth] Login exitoso, datos guardados');

      return response.data;
    } catch (error) {
      console.error('[Auth] Login error:', error.response?.data || error.message);
      const errorMessage = error.response?.data?.detail || 'Error al iniciar sesión';
      toast.error(errorMessage);
      throw error;
    } finally {
      setLoading(false);
      isLoggingIn.current = false;
    }
  }, []);

  // Login directo con datos de usuario (para Google OAuth propio)
  const loginWithUser = useCallback((userData) => {
    if (userData.session_token) {
      localStorage.setItem('session_token', userData.session_token);
    }
    setUser(userData);
    localStorage.setItem('user_data', JSON.stringify(userData));
    setLoading(false);
    console.log('[Auth] Login directo exitoso');
  }, []);

  // Logout - Limpia TODO
  const logout = useCallback(async () => {
    const token = localStorage.getItem('session_token');
    
    try {
      await axios.post(
        `${BACKEND_URL}/api/auth/logout`,
        {},
        { 
          withCredentials: true,
          headers: token ? { Authorization: `Bearer ${token}` } : {}
        }
      );
    } catch (error) {
      console.error('[Auth] Logout error:', error);
    } finally {
      localStorage.removeItem('session_token');
      localStorage.removeItem('user_data');
      setUser(null);
      toast.success('Sesión cerrada');
    }
  }, []);

  // Update user type
  const setUserType = useCallback(async (userType) => {
    try {
      const response = await axios.post(
        `${BACKEND_URL}/api/auth/set-user-type?user_type=${userType}`,
        {},
        { 
          withCredentials: true,
          headers: getAuthHeaders()
        }
      );
      
      setUser(response.data);
      localStorage.setItem('user_data', JSON.stringify(response.data));
      
      return response.data;
    } catch (error) {
      console.error('[Auth] Set user type error:', error);
      throw error;
    }
  }, []);

  // ✅ SOLUCIÓN 5: Función para actualizar usuario localmente
  const updateUser = useCallback((updates) => {
    setUser(prev => {
      const updated = { ...prev, ...updates };
      localStorage.setItem('user_data', JSON.stringify(updated));
      return updated;
    });
  }, []);

  // Check auth on mount - Verificar sesión solo una vez al cargar
  useEffect(() => {
    const hasSessionInUrl = window.location.hash.includes('session_id=');
    const isCallbackPage = window.location.pathname === '/auth/callback';
    
    if (!hasSessionInUrl && !isCallbackPage) {
      checkAuth();
    } else {
      setLoading(false);
    }
  }, []); // ✅ Sin dependencias, solo se ejecuta una vez

  // ✅ SOLUCIÓN 6: NO hay listener de visibilitychange
  // La sesión NO se valida al cambiar de tab

  const value = {
    user,
    loading,
    isAuthenticated: !!user,
    login,
    loginWithUser,
    logout,
    checkAuth,
    setUser: updateUser, // Usar la función actualizada
    setUserType,
    getAuthHeaders
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth debe usarse dentro de AuthProvider');
  }
  return context;
};

// Export helper for use outside React components
export { getAuthHeaders };
