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
  // Initialize user from localStorage cache if available
  const [user, setUser] = useState(() => {
    try {
      const cachedUser = localStorage.getItem('cached_user');
      return cachedUser ? JSON.parse(cachedUser) : null;
    } catch {
      return null;
    }
  });
  const [loading, setLoading] = useState(true);
  const isLoggingIn = useRef(false);

  // Check existing session on mount
  const checkAuth = useCallback(async () => {
    if (isLoggingIn.current) {
      return null;
    }
    
    const token = localStorage.getItem('session_token');
    
    // Si no hay token, no hay sesión
    if (!token) {
      setUser(null);
      localStorage.removeItem('cached_user');
      setLoading(false);
      return null;
    }
    
    // If we already have user data, don't check again
    if (user) {
      setLoading(false);
      return user;
    }
    
    try {
      setLoading(true);
      const response = await axios.get(`${BACKEND_URL}/api/auth/me`, {
        timeout: 15000,
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });
      
      setUser(response.data);
      // Cache user data for faster subsequent loads
      localStorage.setItem('cached_user', JSON.stringify(response.data));
      setLoading(false);
      return response.data;
    } catch (error) {
      console.log('[Auth] Session check failed:', error.message);
      // Only clear token on 401 errors (unauthorized)
      if (error.response?.status === 401) {
        localStorage.removeItem('session_token');
        localStorage.removeItem('cached_user');
        setUser(null);
      } else {
        // For network errors, timeout, etc. - keep the token for retry
        console.log('[Auth] Network error, keeping session token for retry');
      }
      setLoading(false);
      return null;
    }
  }, []);

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

      // Guardar token si viene en la respuesta
      if (response.data.session_token) {
        localStorage.setItem('session_token', response.data.session_token);
      }

      setUser(response.data);
      // Cache user data
      localStorage.setItem('cached_user', JSON.stringify(response.data));
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
    // Cache user data
    localStorage.setItem('cached_user', JSON.stringify(userData));
    setLoading(false);
  }, []);

  // Logout - only clears session when user explicitly logs out
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
      localStorage.removeItem('cached_user');
      // Don't clear disclaimer_seen - user shouldn't see it again
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
      // Update cache
      localStorage.setItem('cached_user', JSON.stringify(response.data));
      return response.data;
    } catch (error) {
      console.error('[Auth] Set user type error:', error);
      throw error;
    }
  }, []);

  // Check auth on mount - but preserve session across refreshes
  useEffect(() => {
    const hasSessionInUrl = window.location.hash.includes('session_id=');
    const isCallbackPage = window.location.pathname === '/auth/callback';
    
    if (!hasSessionInUrl && !isCallbackPage) {
      checkAuth();
    } else {
      setLoading(false);
    }
  }, [checkAuth]);

  const value = {
    user,
    loading,
    isAuthenticated: !!user,
    login,
    loginWithUser,
    logout,
    checkAuth,
    setUser,
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
