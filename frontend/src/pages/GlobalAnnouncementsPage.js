import { useState, useEffect } from 'react';
import { api } from '../config/api';
import { useNavigate } from 'react-router-dom';
import { 
  Megaphone, Calendar, ExternalLink, ChevronRight, Sparkles, 
  Store, Clock, ArrowRight, Star, Gift, Zap
} from 'lucide-react';
import Header from '../components/Header';
import BottomNav from '../components/BottomNav';
import AnimatedBackground from '../components/AnimatedBackground';
import GalacticLoader from '../components/GalacticLoader';

const GlobalAnnouncementsPage = () => {
  const navigate = useNavigate();
  const [announcements, setAnnouncements] = useState([]);
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      try {
        // Get current user
        const userRes = await api.get('/api/auth/me').catch(() => ({ data: null }));
        setUser(userRes.data);
        
        // Los anuncios globales son los featured ads de las pulperías
        const response = await api.get('/api/featured-ads').catch(() => ({ data: [] }));
        setAnnouncements(response.data || []);
      } catch (error) {
        console.error('Error fetching announcements:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, []);

  const formatDate = (dateStr) => {
    if (!dateStr) return '';
    const date = new Date(dateStr);
    return date.toLocaleDateString('es-HN', { 
      day: 'numeric', 
      month: 'short',
      year: 'numeric'
    });
  };

  const cartCount = JSON.parse(localStorage.getItem('cart') || '[]').length;

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-b from-stone-950 via-stone-900 to-stone-950">
        <AnimatedBackground variant="minimal" />
        <GalacticLoader text="Cargando anuncios..." />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-b from-stone-950 via-stone-900 to-stone-950 pb-24">
      <AnimatedBackground variant="minimal" />
      
      <Header 
        user={user} 
        title="Anuncios" 
        subtitle="Ofertas y novedades"
      />

      {/* Hero Section */}
      <div className="relative z-10 px-4 py-6">
        <div className="bg-gradient-to-r from-orange-600/20 to-amber-600/20 backdrop-blur-xl rounded-2xl border border-orange-500/30 p-4 mb-6">
          <div className="flex items-center gap-3">
            <div className="w-12 h-12 bg-gradient-to-br from-orange-500 to-amber-500 rounded-xl flex items-center justify-center shadow-lg shadow-orange-500/30">
              <Megaphone className="w-6 h-6 text-white" />
            </div>
            <div>
              <h2 className="text-lg font-black text-white">Anuncios Globales</h2>
              <p className="text-sm text-orange-300">Ofertas de nuestras pulperías</p>
            </div>
          </div>
        </div>

        {/* Announcements */}
        <div className="space-y-4">
          {announcements.length === 0 ? (
            <div className="bg-stone-800/50 backdrop-blur-sm rounded-2xl border border-stone-700/50 p-8 text-center">
              <Megaphone className="w-12 h-12 mx-auto text-stone-600 mb-3" />
              <h3 className="text-white font-bold mb-2">Sin anuncios</h3>
              <p className="text-stone-500 text-sm">No hay anuncios activos en este momento</p>
            </div>
          ) : (
            announcements.map((ad) => (
              <div 
                key={ad.ad_id}
                className="bg-stone-800/50 backdrop-blur-sm rounded-2xl border border-stone-700/50 overflow-hidden transition-all hover:border-orange-500/50"
              >
                {/* Badge */}
                <div className="bg-gradient-to-r from-orange-600 to-amber-500 px-4 py-1.5 flex items-center gap-2">
                  <Sparkles className="w-4 h-4 text-white" />
                  <span className="text-white text-xs font-bold">ANUNCIO GLOBAL</span>
                </div>
                
                {/* Image - Fixed aspect ratio */}
                {ad.image_url && (
                  <div className="relative bg-stone-900 aspect-video">
                    <img 
                      src={ad.image_url} 
                      alt={ad.title || ad.pulperia_name || 'Anuncio'}
                      className="w-full h-full object-cover"
                    />
                  </div>
                )}
                
                {/* Content */}
                <div className="p-4">
                  <h3 className="text-lg font-bold text-white mb-2">
                    {ad.title || ad.pulperia_name}
                  </h3>
                  
                  {ad.description && (
                    <p className="text-stone-400 text-sm mb-4 whitespace-pre-wrap">
                      {ad.description}
                    </p>
                  )}
                  
                  {/* Footer */}
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2 text-xs text-stone-500">
                      <Store className="w-3 h-3" />
                      <span>{ad.pulperia_name}</span>
                      <span className="mx-1">•</span>
                      <Calendar className="w-3 h-3" />
                      {formatDate(ad.created_at)}
                    </div>
                    
                    <button
                      onClick={() => navigate(`/pulperia/${ad.pulperia_id}`)}
                      className="flex items-center gap-1 text-orange-400 text-sm font-medium hover:text-orange-300 transition-colors"
                    >
                      Ver tienda
                      <ChevronRight className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              </div>
            ))
          )}
        </div>

        {/* Quick Access Section */}
        <div className="mt-8">
          <h3 className="text-white font-bold mb-4 flex items-center gap-2">
            <Gift className="w-5 h-5 text-orange-400" />
            Acceso Rápido
          </h3>
          
          <div className="grid grid-cols-2 gap-3">
            <button
              onClick={() => navigate('/map')}
              className="bg-stone-800/50 backdrop-blur-sm rounded-xl border border-stone-700/50 p-4 text-left hover:border-red-500/50 transition-all"
            >
              <div className="w-10 h-10 bg-red-500/20 rounded-lg flex items-center justify-center mb-3">
                <Store className="w-5 h-5 text-red-400" />
              </div>
              <p className="text-white font-bold text-sm">Ver Pulperías</p>
              <p className="text-stone-500 text-xs">Explora el mapa</p>
            </button>
            
            <button
              onClick={() => navigate('/jobs')}
              className="bg-stone-800/50 backdrop-blur-sm rounded-xl border border-stone-700/50 p-4 text-left hover:border-yellow-500/50 transition-all"
            >
              <div className="w-10 h-10 bg-yellow-500/20 rounded-lg flex items-center justify-center mb-3">
                <Zap className="w-5 h-5 text-yellow-400" />
              </div>
              <p className="text-white font-bold text-sm">Chambas</p>
              <p className="text-stone-500 text-xs">Empleos y servicios</p>
            </button>
          </div>
        </div>
      </div>

      <BottomNav user={user} cartCount={cartCount} activeTab="anuncios" />
    </div>
  );
};

export default GlobalAnnouncementsPage;
