import React, { useMemo } from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import GalacticLoader from './GalacticLoader';

// REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH
const ProtectedRoute = ({ children }) => {
  const location = useLocation();
  const { user, loading } = useAuth();
  
  // If user data was passed from AuthCallback, use it immediately
  const hasUserFromCallback = useMemo(() => !!location.state?.user, [location.state?.user]);
  
  // Check if we have a session token stored (indicates we might be authenticated)
  // Check this on every render, not just mount
  const hasStoredToken = !!localStorage.getItem('session_token');
  
  // Determine authentication status
  const isAuthenticated = hasUserFromCallback || !!user;

  // Show loading when we're verifying auth and we have a token
  const shouldShowLoader = loading && hasStoredToken;

  if (shouldShowLoader) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-stone-950 relative overflow-hidden">
        {/* Nebulosa de fondo */}
        <div 
          className="absolute inset-0"
          style={{
            background: `
              radial-gradient(ellipse 100% 80% at 30% 50%, rgba(220, 38, 38, 0.15), transparent 50%),
              radial-gradient(ellipse 80% 60% at 70% 40%, rgba(250, 204, 21, 0.1), transparent 45%)
            `
          }}
        />
        {/* Estrellas */}
        <div 
          className="absolute inset-0 animate-twinkle opacity-50"
          style={{
            backgroundImage: `
              radial-gradient(1.5px 1.5px at 10% 20%, rgba(255,255,255,0.6), transparent),
              radial-gradient(1px 1px at 50% 30%, rgba(255,255,255,0.5), transparent),
              radial-gradient(1.5px 1.5px at 90% 45%, rgba(255,255,255,0.5), transparent)
            `
          }}
        />
        <div className="relative z-10">
          <GalacticLoader size="default" text="Verificando sesión..." />
        </div>
      </div>
    );
  }

  // If we have a token and user data, allow access
  if (hasStoredToken && isAuthenticated) {
    return children;
  }
  
  // If we have a token but no user data yet and not loading, wait
  if (hasStoredToken && !isAuthenticated && !loading) {
    // Token exists but user data hasn't loaded - this shouldn't normally happen
    // but if it does, show loader briefly while context catches up
    return (
      <div className="min-h-screen flex items-center justify-center bg-stone-950">
        <GalacticLoader size="default" text="Cargando..." />
      </div>
    );
  }

  // No token and not authenticated - redirect to login
  if (!hasStoredToken && !isAuthenticated) {
    return <Navigate to="/" replace />;
  }

  // Default: allow access if authenticated
  return isAuthenticated ? children : <Navigate to="/" replace />;
};

export default ProtectedRoute;
