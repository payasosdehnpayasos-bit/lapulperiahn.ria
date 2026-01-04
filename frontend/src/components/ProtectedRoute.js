import React from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import GalacticLoader from './GalacticLoader';

const ProtectedRoute = ({ children }) => {
  const location = useLocation();
  const { user, loading } = useAuth();
  
  // If user data was passed from AuthCallback, use it immediately
  const hasUserFromCallback = !!location.state?.user;
  
  // Check if we have a session token
  const hasToken = !!localStorage.getItem('session_token');
  
  // Show loader while checking auth
  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-stone-950 relative overflow-hidden">
        <div 
          className="absolute inset-0"
          style={{
            background: `
              radial-gradient(ellipse 100% 80% at 30% 50%, rgba(220, 38, 38, 0.15), transparent 50%),
              radial-gradient(ellipse 80% 60% at 70% 40%, rgba(250, 204, 21, 0.1), transparent 45%)
            `
          }}
        />
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

  // Allow access if authenticated
  if (user || hasUserFromCallback) {
    return children;
  }

  // Redirect to login if no token and not authenticated
  if (!hasToken && !user) {
    return <Navigate to="/" replace />;
  }

  // Default: allow access (optimistic - let API calls handle auth errors)
  return children;
};

export default ProtectedRoute;
