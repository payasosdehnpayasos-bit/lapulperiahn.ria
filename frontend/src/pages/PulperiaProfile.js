import { useState, useEffect, useCallback } from 'react';
import { useParams } from 'react-router-dom';
import { api, BACKEND_URL } from '../config/api';
import { toast } from 'sonner';
import { MapPin, Phone, Clock, Plus, Minus, ShoppingCart, ArrowLeft, Star, Send, Camera, Check, X, Briefcase, Mail, Globe, DollarSign, Package, Megaphone, Image, Heart, ZoomIn, Wifi, Share2, Copy } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import BottomNav from '../components/BottomNav';
import AnimatedBackground from '../components/AnimatedBackground';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../components/ui/dialog';
import { Textarea } from '../components/ui/textarea';
import { Button } from '../components/ui/button';
import { Label } from '../components/ui/label';


const FONT_CLASSES = {
  default: 'font-black',
  serif: 'font-serif font-bold',
  script: 'font-serif italic',
  bold: 'font-extrabold tracking-tight'
};

// Achievement definitions (same as backend)
const ACHIEVEMENT_INFO = {
  primera_venta: { name: "Primera Venta", icon: "🛒", color: "from-green-600 to-green-500" },
  catalogo_inicial: { name: "Catálogo Inicial", icon: "📦", color: "from-blue-600 to-blue-500" },
  diez_ventas: { name: "10 Ventas", icon: "⭐", color: "from-amber-600 to-amber-500" },
  catalogo_completo: { name: "Catálogo Completo", icon: "📦", color: "from-blue-600 to-blue-500" },
  primeras_visitas: { name: "Ganando Visibilidad", icon: "👁", color: "from-purple-600 to-purple-500" },
  cliente_feliz: { name: "Clientes Felices", icon: "❤️", color: "from-red-600 to-red-500" },
  cincuenta_ventas: { name: "Vendedor Activo", icon: "📈", color: "from-green-600 to-green-500" },
  popular: { name: "Pulpería Popular", icon: "👥", color: "from-indigo-600 to-indigo-500" },
  cien_ventas: { name: "Vendedor Estrella", icon: "🌟", color: "from-amber-600 to-amber-500" },
  super_catalogo: { name: "Super Catálogo", icon: "📚", color: "from-cyan-600 to-cyan-500" },
  muy_popular: { name: "Muy Popular", icon: "🔥", color: "from-orange-600 to-orange-500" },
  verificado: { name: "Verificado", icon: "✓", color: "from-emerald-600 to-emerald-500", legendary: true },
  top_vendedor: { name: "Top Vendedor", icon: "🏆", color: "from-yellow-500 to-amber-400", legendary: true },
  leyenda: { name: "Leyenda Local", icon: "👑", color: "from-yellow-400 to-amber-300", legendary: true }
};

// Modal para ver imagen completa
const ImageViewerModal = ({ imageUrl, productName, onClose }) => {
  if (!imageUrl) return null;
  
  return (
    <div 
      className="fixed inset-0 z-[9999] bg-black/95 flex items-center justify-center p-4"
      onClick={onClose}
    >
      <button 
        onClick={onClose}
        className="absolute top-4 right-4 p-3 bg-white/10 hover:bg-white/20 rounded-full transition-colors"
      >
        <X className="w-6 h-6 text-white" />
      </button>
      <img 
        src={imageUrl} 
        alt={productName}
        className="max-w-full max-h-[85vh] object-contain rounded-lg"
        onClick={(e) => e.stopPropagation()}
      />
      <p className="absolute bottom-6 left-0 right-0 text-center text-white font-medium">
        {productName}
      </p>
    </div>
  );
};

const PulperiaProfile = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const [user, setUser] = useState(null);
  const [pulperia, setPulperia] = useState(null);
  const [products, setProducts] = useState([]);
  const [reviews, setReviews] = useState([]);
  const [jobs, setJobs] = useState([]);
  const [achievements, setAchievements] = useState([]);
  const [loading, setLoading] = useState(true);
  const [cart, setCart] = useState([]);
  const [showReviewDialog, setShowReviewDialog] = useState(false);
  const [rating, setRating] = useState(5);
  const [comment, setComment] = useState('');
  const [hasReviewed, setHasReviewed] = useState(false);
  const [activeTab, setActiveTab] = useState('products');
  const [showLogoModal, setShowLogoModal] = useState(false);
  const [announcements, setAnnouncements] = useState([]);
  const [isFavorite, setIsFavorite] = useState(false);
  const [togglingFavorite, setTogglingFavorite] = useState(false);
  const [viewingImage, setViewingImage] = useState(null);
  const [viewingAnnouncement, setViewingAnnouncement] = useState(null);
  const [showShareDialog, setShowShareDialog] = useState(false);

  // Check if favorite
  const checkFavorite = useCallback(async () => {
    try {
      const response = await api.get(`/api/favorites/${id}/check`);
      setIsFavorite(response.data.is_favorite);
    } catch (e) { /* ignore */ }
  }, [id]);

  // Toggle favorite
  const toggleFavorite = async () => {
    if (togglingFavorite) return;
    setTogglingFavorite(true);
    try {
      if (isFavorite) {
        await api.delete(`/api/favorites/${id}`);
        setIsFavorite(false);
        toast.success('Eliminado de favoritos');
      } else {
        await api.post(`/api/favorites/${id}`, {});
        setIsFavorite(true);
        toast.success('Agregado a favoritos');
      }
    } catch (error) {
      toast.error('Error al actualizar favoritos');
    } finally {
      setTogglingFavorite(false);
    }
  };

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [userRes, pulperiaRes, productsRes, reviewsRes, jobsRes, achievementsRes] = await Promise.all([
          api.get(`/api/auth/me`),
          api.get(`/api/pulperias/${id}`),
          api.get(`/api/pulperias/${id}/products`),
          api.get(`/api/pulperias/${id}/reviews`),
          api.get(`/api/pulperias/${id}/jobs`).catch(() => ({ data: [] })),
          api.get(`/api/pulperias/${id}/achievements`).catch(() => ({ data: [] }))
        ]);
        
        setUser(userRes.data);
        setPulperia(pulperiaRes.data);
        setProducts(productsRes.data.filter(p => p.available !== false));
        setReviews(reviewsRes.data);
        setJobs(jobsRes.data);
        setAchievements(achievementsRes.data);
        
        // Fetch announcements
        try {
          const announcementsRes = await api.get(`/api/pulperias/${id}/announcements`);
          setAnnouncements(announcementsRes.data);
        } catch (e) {
          setAnnouncements([]);
        }
        
        // Check if favorite
        checkFavorite();
        
        // Increment view count
        try {
          await api.post(`/api/pulperias/${id}/view`);
        } catch (e) { /* ignore */ }
        
        const userReview = reviewsRes.data.find(r => r.user_id === userRes.data.user_id);
        setHasReviewed(!!userReview);
        
        try {
          const savedCart = localStorage.getItem('cart');
          if (savedCart) setCart(JSON.parse(savedCart));
        } catch (e) {
          localStorage.removeItem('cart');
        }
      } catch (error) {
        console.error('Error:', error);
        toast.error('Error al cargar');
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, [id, checkFavorite]);

  // Save cart with minimal data
  const saveCart = (newCart) => {
    try {
      const minimalCart = newCart.map(item => ({
        product_id: item.product_id,
        name: item.name,
        price: item.price,
        quantity: item.quantity,
        pulperia_id: item.pulperia_id,
        pulperia_name: item.pulperia_name
      }));
      localStorage.setItem('cart', JSON.stringify(minimalCart));
    } catch (e) {
      if (e.name === 'QuotaExceededError') {
        localStorage.removeItem('cart');
        toast.error('Carrito reiniciado');
      }
    }
  };

  const addToCart = (product) => {
    const existingItem = cart.find(item => item.product_id === product.product_id);
    let newCart;
    
    if (existingItem) {
      newCart = cart.map(item =>
        item.product_id === product.product_id
          ? { ...item, quantity: item.quantity + 1 }
          : item
      );
    } else {
      newCart = [...cart, {
        product_id: product.product_id,
        name: product.name,
        price: product.price,
        quantity: 1,
        pulperia_id: id,
        pulperia_name: pulperia?.name || 'Pulpería',
        image_url: product.image_url || null
      }];
    }
    
    setCart(newCart);
    saveCart(newCart);
    toast.success(`${product.name} agregado`);
  };

  const removeFromCart = (productId) => {
    const existingItem = cart.find(item => item.product_id === productId);
    let newCart;
    
    if (existingItem && existingItem.quantity > 1) {
      newCart = cart.map(item =>
        item.product_id === productId
          ? { ...item, quantity: item.quantity - 1 }
          : item
      );
    } else {
      newCart = cart.filter(item => item.product_id !== productId);
    }
    
    setCart(newCart);
    saveCart(newCart);
  };

  const getCartQuantity = (productId) => {
    const item = cart.find(item => item.product_id === productId);
    return item ? item.quantity : 0;
  };

  const handleSubmitReview = async () => {
    if (rating < 1 || rating > 5) {
      toast.error('Rating debe estar entre 1 y 5');
      return;
    }

    try {
      await api.post(`/api/pulperias/${id}/reviews`, {
        rating,
        comment,
        images: []
      });

      toast.success('¡Gracias por tu review!');
      setShowReviewDialog(false);
      setHasReviewed(true);
      
      const reviewsRes = await api.get(`/api/pulperias/${id}/reviews`);
      setReviews(reviewsRes.data);
      
      const pulperiaRes = await api.get(`/api/pulperias/${id}`);
      setPulperia(pulperiaRes.data);
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Error al enviar review');
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-red-900 via-red-800 to-red-900">
        <div className="text-center">
          <div className="w-16 h-16 border-4 border-red-400/30 rounded-full animate-spin border-t-white mx-auto"></div>
          <p className="text-white/80 mt-4 font-medium">Cargando...</p>
        </div>
      </div>
    );
  }

  if (!pulperia) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-red-900 via-red-800 to-red-900">
        <p className="text-white/70">Pulpería no encontrada</p>
      </div>
    );
  }

  const bgColor = pulperia.background_color || '#DC2626';
  const fontClass = FONT_CLASSES[pulperia.title_font] || FONT_CLASSES.default;
  const cartCount = cart.reduce((sum, item) => sum + item.quantity, 0);
  const isOnlineOnly = pulperia.is_online_only;

  return (
    <div className="min-h-screen bg-stone-950 pb-24">
      <AnimatedBackground variant="minimal" />
      
      {/* Banner - estilo X/Facebook con imagen ajustada */}
      <div className="relative h-48 md:h-56 overflow-hidden">
        {pulperia.banner_url ? (
          <img 
            src={pulperia.banner_url} 
            alt="Banner" 
            className="w-full h-full object-cover object-center"
          />
        ) : (
          <div 
            className="w-full h-full"
            style={{ background: `linear-gradient(135deg, ${bgColor} 0%, ${bgColor}99 50%, #1c1917 100%)` }}
          />
        )}
        <div className="absolute inset-0 bg-gradient-to-t from-stone-900 via-stone-900/40 to-transparent" />
        
        <button onClick={() => navigate(-1)} className="absolute top-4 left-4 bg-black/40 backdrop-blur-sm p-2.5 rounded-full text-white hover:bg-black/60 transition-all z-10">
          <ArrowLeft className="w-5 h-5" />
        </button>
        
        {/* Action buttons */}
        <div className="absolute top-4 right-4 flex gap-2 z-10">
          {/* Share Button */}
          <button 
            onClick={() => setShowShareDialog(true)}
            className="backdrop-blur-sm bg-black/40 text-white hover:bg-black/60 p-2.5 rounded-full transition-all"
          >
            <Share2 className="w-5 h-5" />
          </button>
          
          {/* Favorite Button */}
          <button 
            onClick={toggleFavorite}
            disabled={togglingFavorite}
            className={`backdrop-blur-sm p-2.5 rounded-full transition-all ${
              isFavorite 
                ? 'bg-red-500 text-white' 
                : 'bg-black/40 text-white hover:bg-black/60'
            }`}
          >
            <Heart className={`w-5 h-5 ${isFavorite ? 'fill-current' : ''}`} />
          </button>
        </div>
        
        {/* Online Only Badge */}
        {isOnlineOnly && (
          <div className="absolute top-4 left-1/2 -translate-x-1/2 bg-gradient-to-r from-cyan-600 to-blue-600 text-white px-3 py-1.5 rounded-full flex items-center gap-1.5 shadow-lg z-10">
            <Wifi className="w-4 h-4" />
            <span className="text-sm font-bold">Solo en línea</span>
          </div>
        )}
      </div>

      {/* Profile Photo - Clickeable */}
      <div className="relative px-6 -mt-16">
        <div className="flex items-end gap-3">
          {pulperia.logo_url ? (
            <button 
              onClick={() => setShowLogoModal(true)}
              className="relative group"
            >
              <img 
                src={pulperia.logo_url} 
                alt={pulperia.name} 
                className="w-28 h-28 rounded-2xl border-4 border-stone-800 shadow-2xl object-cover cursor-pointer hover:scale-105 transition-transform"
              />
              <div className="absolute inset-0 bg-black/0 group-hover:bg-black/20 rounded-2xl transition-colors flex items-center justify-center">
                <Image className="w-6 h-6 text-white opacity-0 group-hover:opacity-100 transition-opacity" />
              </div>
            </button>
          ) : (
            <div 
              className="w-28 h-28 rounded-2xl border-4 border-stone-800 shadow-2xl flex items-center justify-center"
              style={{ backgroundColor: bgColor }}
            >
              <Package className="w-12 h-12 text-white/70" />
            </div>
          )}
        </div>
      </div>

      {/* Logo Modal */}
      <Dialog open={showLogoModal} onOpenChange={setShowLogoModal}>
        <DialogContent className="bg-transparent border-0 shadow-none max-w-3xl">
          <div className="relative">
            <button 
              onClick={() => setShowLogoModal(false)}
              className="absolute -top-12 right-0 p-2 bg-black/50 rounded-full text-white hover:bg-black/70 transition-colors"
            >
              <X className="w-6 h-6" />
            </button>
            <img 
              src={pulperia.logo_url} 
              alt={pulperia.name} 
              className="w-full max-h-[80vh] object-contain rounded-2xl"
            />
          </div>
        </DialogContent>
      </Dialog>

      {/* Info */}
      <div className="px-6 pt-4 pb-4">
        <h1 className={`text-2xl ${fontClass} text-white`}>{pulperia.name}</h1>
        
        {pulperia.rating > 0 && (
          <div className="flex items-center gap-1 mt-2">
            <Star className="w-5 h-5 fill-amber-400 text-amber-400" />
            <span className="font-bold text-white">{pulperia.rating.toFixed(1)}</span>
            <span className="text-stone-400 text-sm">({pulperia.review_count} reviews)</span>
          </div>
        )}

        <div className="flex flex-wrap gap-3 mt-3 text-sm text-stone-400">
          {isOnlineOnly ? (
            <div className="flex items-center gap-1.5 text-cyan-400">
              <Wifi className="w-4 h-4" />
              <span>Tienda solo en línea</span>
            </div>
          ) : pulperia.address && (
            <a 
              href={pulperia.location?.lat && pulperia.location?.lng 
                ? `https://www.google.com/maps/dir/?api=1&destination=${pulperia.location.lat},${pulperia.location.lng}`
                : `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(pulperia.address)}`
              }
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1.5 hover:text-red-400 transition-colors cursor-pointer"
            >
              <MapPin className="w-4 h-4 text-red-400" />
              <span className="underline underline-offset-2">{pulperia.address}</span>
            </a>
          )}
          {pulperia.phone && (
            <a href={`tel:${pulperia.phone}`} className="flex items-center gap-1.5 text-green-400 hover:text-green-300"><Phone className="w-4 h-4" />{pulperia.phone}</a>
          )}
        </div>
      </div>

      {/* Tabs - Now includes Logros */}
      <div className="px-4 mb-4">
        <div className="flex bg-stone-900 rounded-xl p-1 border border-stone-800 overflow-x-auto">
          {['products', 'anuncios', 'empleos', 'reviews', 'logros'].map(tab => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`flex-1 py-2.5 px-3 rounded-lg text-sm font-medium transition-all whitespace-nowrap ${
                activeTab === tab ? 'bg-red-600 text-white' : 'text-stone-500 hover:text-white'
              }`}
            >
              {tab === 'products' ? `Productos` : 
               tab === 'anuncios' ? `Anuncios` :
               tab === 'empleos' ? `Empleos` : 
               tab === 'reviews' ? `Reviews` :
               `Logros`}
            </button>
          ))}
        </div>
      </div>

      {/* Content */}
      <div className="px-4">
        {activeTab === 'products' && (
          <div className="grid grid-cols-2 gap-4">
            {products.map(product => {
              const qty = getCartQuantity(product.product_id);
              return (
                <div key={product.product_id} className="product-card-galactic group">
                  {/* Imagen del producto - Más grande */}
                  <div 
                    className="product-image-container h-44 bg-gradient-to-br from-stone-900 to-stone-950 flex items-center justify-center cursor-pointer"
                    onClick={() => product.image_url && setViewingImage({ url: product.image_url, name: product.name })}
                  >
                    {product.image_url ? (
                      <>
                        <img src={product.image_url} alt={product.name} className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300" />
                        <div className="absolute inset-0 bg-black/0 group-hover:bg-black/30 transition-colors flex items-center justify-center">
                          <ZoomIn className="w-8 h-8 text-white opacity-0 group-hover:opacity-100 transition-opacity" />
                        </div>
                      </>
                    ) : (
                      <Package className="w-10 h-10 text-stone-700" />
                    )}
                  </div>
                  <div className="p-4">
                    <h3 className="font-semibold text-white truncate">{product.name}</h3>
                    <div className="flex items-center justify-between mt-2">
                      <p className="gradient-text font-bold text-xl">L{product.price.toFixed(0)}</p>
                      {product.category && (
                        <span className="text-xs text-stone-500 bg-stone-800/50 px-2 py-1 rounded-full">{product.category}</span>
                      )}
                    </div>
                    
                    {qty > 0 ? (
                      <div className="flex items-center justify-between mt-3 bg-gradient-to-r from-stone-800/80 to-stone-900/80 rounded-xl border border-red-500/20">
                        <button onClick={() => removeFromCart(product.product_id)} className="p-2.5 hover:bg-red-500/20 rounded-l-xl transition-colors">
                          <Minus className="w-4 h-4 text-red-400" />
                        </button>
                        <span className="font-bold text-white">{qty}</span>
                        <button onClick={() => addToCart(product)} className="p-2.5 hover:bg-red-500/20 rounded-r-xl transition-colors">
                          <Plus className="w-4 h-4 text-red-400" />
                        </button>
                      </div>
                    ) : (
                      <button onClick={() => addToCart(product)} className="w-full mt-3 galactic-button text-white py-2.5 rounded-xl text-sm font-bold transition-all">
                        Agregar al Carrito
                      </button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {activeTab === 'empleos' && (
          <div className="space-y-3">
            {jobs.length === 0 ? (
              <p className="text-center text-stone-600 py-8">No hay empleos disponibles</p>
            ) : (
              jobs.map(job => (
                <div key={job.job_id} className="galactic-card rounded-xl p-4">
                  <h3 className="font-medium text-white">{job.title}</h3>
                  <p className="text-stone-500 text-sm mt-1">{job.description}</p>
                  <div className="flex items-center gap-2 mt-2 text-sm">
                    <DollarSign className="w-4 h-4 text-green-400" />
                    <span className="font-bold text-green-400">L{job.pay_rate}/{job.pay_currency}</span>
                  </div>
                  {job.location && (
                    <div className="flex items-center gap-2 mt-2 text-sm">
                      <MapPin className="w-4 h-4 text-amber-400" />
                      <span className="text-stone-400">{job.location}</span>
                    </div>
                  )}
                </div>
              ))
            )}
          </div>
        )}

        {/* Anuncios - Redesigned as professional ad cards with full images */}
        {activeTab === 'anuncios' && (
          <div className="space-y-4">
            {announcements.length === 0 ? (
              <div className="text-center py-12 bg-stone-900/50 rounded-2xl border border-stone-800">
                <Megaphone className="w-10 h-10 text-stone-700 mx-auto mb-3" />
                <p className="text-stone-500">No hay anuncios publicados</p>
              </div>
            ) : (
              announcements.map(announcement => (
                <div 
                  key={announcement.announcement_id} 
                  className="bg-gradient-to-br from-stone-900 to-stone-800 rounded-2xl border border-stone-700 overflow-hidden shadow-xl"
                >
                  {/* Ad Banner Style Header */}
                  <div className="bg-gradient-to-r from-red-600/20 to-orange-600/20 px-4 py-2 flex items-center gap-2 border-b border-stone-700/50">
                    <Megaphone className="w-4 h-4 text-orange-400" />
                    <span className="text-orange-400 text-xs font-bold uppercase tracking-wider">Anuncio</span>
                    <span className="text-stone-500 text-xs ml-auto">
                      {new Date(announcement.created_at).toLocaleDateString('es-HN')}
                    </span>
                  </div>
                  
                  {/* Full Image Display */}
                  {announcement.image_url && (
                    <div 
                      className="cursor-pointer"
                      onClick={() => setViewingAnnouncement(announcement)}
                    >
                      <img 
                        src={announcement.image_url} 
                        alt="Anuncio" 
                        className="w-full object-contain max-h-[400px] bg-stone-950"
                      />
                    </div>
                  )}
                  
                  {/* Content */}
                  <div className="p-4">
                    <div className="flex items-center gap-3 mb-3">
                      {pulperia.logo_url && (
                        <img src={pulperia.logo_url} alt={pulperia.name} className="w-10 h-10 rounded-full object-cover border-2 border-stone-600" />
                      )}
                      <div>
                        <p className="font-bold text-white">{pulperia.name}</p>
                        <p className="text-stone-500 text-xs">Publicidad</p>
                      </div>
                    </div>
                    
                    <p className="text-white text-base leading-relaxed">{announcement.content}</p>
                    
                    {announcement.tags && announcement.tags.length > 0 && (
                      <div className="flex flex-wrap gap-2 mt-4">
                        {announcement.tags.map((tag, i) => (
                          <span key={i} className="text-xs bg-red-900/50 text-red-400 px-2 py-1 rounded-full border border-red-700/50">
                            #{tag}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              ))
            )}
          </div>
        )}

        {activeTab === 'reviews' && (
          <div className="space-y-3">
            {user?.user_type === 'cliente' && !hasReviewed && (
              <button onClick={() => setShowReviewDialog(true)} className="w-full bg-gradient-to-r from-red-600 to-red-500 text-white py-3 rounded-xl font-bold shadow-lg shadow-red-900/30">
                Dejar Review
              </button>
            )}
            
            {reviews.length === 0 ? (
              <p className="text-center text-stone-500 py-8">No hay reviews aún</p>
            ) : (
              reviews.map(review => (
                <div key={review.review_id} className="bg-stone-800/50 backdrop-blur-sm rounded-xl p-4 border border-stone-700/50">
                  <div className="flex items-center gap-2">
                    <div className="font-bold text-white">{review.user_name}</div>
                    <div className="flex items-center">
                      {[...Array(5)].map((_, i) => (
                        <Star key={i} className={`w-4 h-4 ${i < review.rating ? 'fill-amber-400 text-amber-400' : 'text-stone-600'}`} />
                      ))}
                    </div>
                  </div>
                  {review.comment && <p className="text-stone-400 text-sm mt-2">{review.comment}</p>}
                </div>
              ))
            )}
          </div>
        )}

        {/* Logros Tab - New */}
        {activeTab === 'logros' && (
          <div className="space-y-4">
            {achievements.length === 0 ? (
              <div className="text-center py-12 bg-stone-900/50 rounded-2xl border border-stone-800">
                <Trophy className="w-12 h-12 text-stone-700 mx-auto mb-3" />
                <p className="text-stone-500">Esta pulpería aún no tiene logros</p>
                <p className="text-stone-600 text-sm mt-1">Los logros se desbloquean con ventas, productos y clientes felices</p>
              </div>
            ) : (
              <div className="grid grid-cols-2 gap-3">
                {achievements.map(ach => {
                  const info = ACHIEVEMENT_INFO[ach.badge_id] || { name: ach.badge_id, icon: '🏅', color: 'from-gray-600 to-gray-500' };
                  return (
                    <div 
                      key={ach.achievement_id}
                      className={`bg-gradient-to-br ${info.color} rounded-2xl p-4 shadow-lg ${info.legendary ? 'ring-2 ring-yellow-400 ring-offset-2 ring-offset-stone-950' : ''}`}
                    >
                      <div className="text-3xl mb-2">{info.icon}</div>
                      <h3 className="font-bold text-white">{info.name}</h3>
                      <p className="text-white/70 text-xs mt-1">
                        {new Date(ach.unlocked_at).toLocaleDateString('es-HN')}
                      </p>
                      {info.legendary && (
                        <div className="mt-2 bg-yellow-400/20 rounded-full px-2 py-0.5 inline-block">
                          <span className="text-yellow-300 text-xs font-bold">✨ Legendario</span>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
            
            {/* Achievement Progress Info */}
            <div className="bg-stone-900/50 rounded-xl p-4 border border-stone-700 mt-4">
              <div className="flex items-center gap-2 mb-2">
                <Award className="w-5 h-5 text-amber-400" />
                <span className="text-white font-bold">Sistema de Meritocracia</span>
              </div>
              <p className="text-stone-400 text-sm">
                Las pulperías desbloquean logros basados en ventas, productos, visitas y reseñas de clientes. 
                ¡Los logros legendarios son especialmente difíciles de conseguir!
              </p>
            </div>
          </div>
        )}
      </div>

      {/* Review Dialog */}
      <Dialog open={showReviewDialog} onOpenChange={setShowReviewDialog}>
        <DialogContent className="max-w-sm mx-4">
          <DialogHeader>
            <DialogTitle>Dejar Review</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <Label>Rating</Label>
              <div className="flex gap-1 mt-1">
                {[1,2,3,4,5].map(i => (
                  <button key={i} onClick={() => setRating(i)}>
                    <Star className={`w-8 h-8 ${i <= rating ? 'fill-yellow-400 text-yellow-400' : 'text-stone-200'}`} />
                  </button>
                ))}
              </div>
            </div>
            <div>
              <Label>Comentario</Label>
              <Textarea value={comment} onChange={(e) => setComment(e.target.value)} placeholder="Tu opinión..." />
            </div>
            <Button onClick={handleSubmitReview} className="w-full bg-red-600 hover:bg-red-700">Enviar</Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Image Viewer Modal */}
      {viewingImage && (
        <ImageViewerModal 
          imageUrl={viewingImage.url} 
          productName={viewingImage.name} 
          onClose={() => setViewingImage(null)} 
        />
      )}

      {/* Announcement Image Viewer */}
      {viewingAnnouncement && viewingAnnouncement.image_url && (
        <div 
          className="fixed inset-0 z-[9999] bg-black/95 flex items-center justify-center p-4"
          onClick={() => setViewingAnnouncement(null)}
        >
          <button 
            onClick={() => setViewingAnnouncement(null)}
            className="absolute top-4 right-4 p-3 bg-white/10 hover:bg-white/20 rounded-full transition-colors"
          >
            <X className="w-6 h-6 text-white" />
          </button>
          <img 
            src={viewingAnnouncement.image_url} 
            alt="Anuncio"
            className="max-w-full max-h-[90vh] object-contain rounded-lg"
            onClick={(e) => e.stopPropagation()}
          />
        </div>
      )}

      {/* Modal de Compartir */}
      <SharePulperia
        pulperia={pulperia}
        open={showShareDialog}
        onOpenChange={setShowShareDialog}
      />

      <BottomNav user={user} cartCount={cartCount} />
    </div>
  );
};

export default PulperiaProfile;
