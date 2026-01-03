import React, { useMemo, useEffect, useState } from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import GalacticLoader from './GalacticLoader';

// REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH
const ProtectedRoute = ({ children }) => {
  const location = useLocation();
  const { user, loading } = useAuth();
  const [hasAttemptedAuth, setHasAttemptedAuth] = useState(false);
  
  // If user data was passed from AuthCallback, use it immediately
  const hasUserFromCallback = useMemo(() => !!location.state?.user, [location.state?.user]);
  
  // Check if we have a session token stored (indicates we might be authenticated)
  const hasStoredToken = useMemo(() => !!localStorage.getItem('session_token'), []);
  
  // Track when we've finished at least one auth attempt
  useEffect(() => {
    if (!loading && hasStoredToken) {
      setHasAttemptedAuth(true);
    }
  }, [loading, hasStoredToken]);
  
  // Determine authentication status
  const isAuthenticated = hasUserFromCallback || !!user;

  // Show loading ONLY when:
  // 1. We're loading AND
  // 2. We have a token AND
  // 3. We haven't attempted auth yet OR we're still verifying
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

  // Redirect to login if definitely not authenticated
  if (!loading && !isAuthenticated && !hasStoredToken) {
    return <Navigate to="/" replace />;
  }
  
  // If we're authenticated or still checking, render children
  if (isAuthenticated || (loading && hasStoredToken)) {
    return children;
  }

  // Final fallback - redirect to login
  return <Navigate to="/" replace />;
};

export default ProtectedRoute;
