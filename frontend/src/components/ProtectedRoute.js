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
  const hasStoredToken = useMemo(() => !!localStorage.getItem('session_token'), []);
  
  // Determine authentication status
  const isAuthenticated = hasUserFromCallback || !!user;

  // Show loading state ALWAYS when loading AND we have a token
  // This prevents redirecting during token validation
  if (loading && hasStoredToken) {
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

  // Redirect to login only if we're sure user is not authenticated
  // AND no token exists (to prevent false redirects during validation)
  if (!loading && !isAuthenticated && !hasStoredToken) {
    return <Navigate to="/" replace />;
  }

  // If we have a token but still loading, keep showing loader
  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-stone-950 relative overflow-hidden">
        <div className="relative z-10">
          <GalacticLoader size="default" text="Cargando..." />
        </div>
      </div>
    );
  }

  return children;
};

export default ProtectedRoute;
