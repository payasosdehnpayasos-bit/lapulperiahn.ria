import { useNavigate, useLocation } from 'react-router-dom';
import { MapPin, Megaphone, ShoppingCart, User, LayoutDashboard, History, Briefcase } from 'lucide-react';
import MiniNebula from './MiniNebula';

const BottomNav = ({ user, cartCount = 0, activeTab }) => {
  const navigate = useNavigate();
  const location = useLocation();

  const isActive = (path, tabName) => {
    if (activeTab) return activeTab === tabName;
    return location.pathname === path;
  };

  // Determine user type - default to 'customer' if not set
  const userType = user?.user_type || 'customer';
  const isPulperia = userType === 'pulperia';

  // Items fijos para cada tipo de usuario - siempre 5 items
  const navItems = isPulperia ? [
    { icon: LayoutDashboard, label: 'Dashboard', path: '/dashboard', testId: 'nav-dashboard', tab: 'dashboard' },
    { icon: Briefcase, label: 'Chamba', path: '/jobs', testId: 'nav-jobs', tab: 'jobs', isChamba: true },
    { icon: Megaphone, label: 'Anuncios', path: '/anuncios-globales', testId: 'nav-anuncios', tab: 'anuncios', isAnuncios: true },
    { icon: History, label: 'Reportes', path: '/order-history', testId: 'nav-reportes', tab: 'reportes' },
    { icon: User, label: 'Perfil', path: '/profile', testId: 'nav-profile', tab: 'perfil' },
  ] : [
    { icon: MapPin, label: 'Mapa', path: '/map', testId: 'nav-map', tab: 'mapa' },
    { icon: Briefcase, label: 'Chamba', path: '/jobs', testId: 'nav-jobs', tab: 'jobs', isChamba: true },
    { icon: Megaphone, label: 'Anuncios', path: '/anuncios-globales', testId: 'nav-anuncios', tab: 'anuncios', isAnuncios: true },
    { icon: ShoppingCart, label: 'Carrito', path: '/cart', testId: 'nav-cart', tab: 'carrito', badge: cartCount },
    { icon: User, label: 'Perfil', path: '/profile', testId: 'nav-profile', tab: 'perfil' },
  ];

  return (
    <nav className="fixed bottom-0 left-0 right-0 z-50 glass-nebula border-t border-white/10 safe-area-pb overflow-hidden">
      {/* Mini Nebulosa animada */}
      <MiniNebula variant="bottom" intensity="medium" />
      
      {/* Grid fijo de 5 columnas para que los botones no se muevan */}
      <div className="relative grid grid-cols-5 px-1 py-2">
        {navItems.map((item, index) => {
          const Icon = item.icon;
          const active = isActive(item.path, item.tab);
          const isChamba = item.isChamba;
          const isAnuncios = item.isAnuncios;
          
          return (
            <button
              key={item.path}
              onClick={() => navigate(item.path)}
              data-testid={item.testId}
              className={`relative flex flex-col items-center justify-center gap-1 py-2 rounded-xl transition-colors duration-200 ${
                active 
                  ? isChamba ? 'text-yellow-400' : isAnuncios ? 'text-orange-400' : 'text-red-400' 
                  : 'text-stone-500 hover:text-stone-300'
              }`}
            >
              {/* Glow effect for Chamba - Yellow - SOLO cuando está activo */}
              {isChamba && active && (
                <div className="absolute inset-2 rounded-xl blur-md bg-yellow-500/25" />
              )}
              
              {/* Glow effect for Anuncios - Orange - SOLO cuando está activo */}
              {isAnuncios && active && (
                <div className="absolute inset-2 rounded-xl blur-md bg-orange-500/25" />
              )}
              
              {/* Glow effect for active non-Chamba/non-Anuncios */}
              {active && !isChamba && !isAnuncios && (
                <div className="absolute inset-2 bg-red-500/15 rounded-xl blur-sm" />
              )}
              
              <div className="relative">
                {/* Icono con glow especial */}
                <Icon className={`w-5 h-5 transition-transform duration-200 ${active ? 'scale-110' : ''} ${
                  isChamba && active ? 'drop-shadow-[0_0_8px_rgba(250,204,21,0.6)]' : ''
                } ${
                  isAnuncios && active ? 'drop-shadow-[0_0_8px_rgba(251,146,60,0.6)]' : ''
                }`} />
                
                {/* Badge para carrito */}
                {item.badge > 0 && (
                  <span className="absolute -top-1.5 -right-1.5 w-4 h-4 bg-gradient-to-br from-red-500 to-red-700 text-white text-[10px] font-bold rounded-full flex items-center justify-center shadow-lg shadow-red-500/30">
                    {item.badge > 9 ? '9+' : item.badge}
                  </span>
                )}
              </div>
              
              <span className={`text-[10px] font-medium relative ${
                isChamba && active ? 'text-yellow-400' : ''
              } ${
                isAnuncios && active ? 'text-orange-400' : ''
              }`}>
                {item.label}
              </span>
              
              {/* Active indicator - Yellow for Chamba, Orange for Anuncios, Red for others */}
              {active && (
                <div className={`absolute bottom-0.5 left-1/2 -translate-x-1/2 w-1 h-1 rounded-full ${
                  isChamba 
                    ? 'bg-yellow-400 shadow-lg shadow-yellow-400/50' 
                    : isAnuncios
                    ? 'bg-orange-400 shadow-lg shadow-orange-400/50'
                    : 'bg-red-500 shadow-lg shadow-red-500/50'
                }`} />
              )}
            </button>
          );
        })}
      </div>
    </nav>
  );
};

export default BottomNav;
