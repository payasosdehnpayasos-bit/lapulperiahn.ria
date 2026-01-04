import React, { useState, useRef } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../ui/dialog';
import { Button } from '../ui/button';
import { Camera, Upload, X, Loader2 } from 'lucide-react';
import { toast } from 'sonner';
import { api } from '../../config/api';

const ProfilePictureEditor = ({ user, open, onOpenChange, onUpdate }) => {
  const [selectedImage, setSelectedImage] = useState(null);
  const [preview, setPreview] = useState(null);
  const [uploading, setUploading] = useState(false);
  const fileInputRef = useRef(null);

  // Función para comprimir imagen si es muy grande
  const compressImage = (file, maxSizeMB = 10) => {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      
      reader.onload = (e) => {
        const img = new Image();
        img.onload = () => {
          const canvas = document.createElement('canvas');
          let width = img.width;
          let height = img.height;
          
          // Redimensionar si es muy grande (máximo 2000px)
          const maxDimension = 2000;
          if (width > maxDimension || height > maxDimension) {
            if (width > height) {
              height = (height / width) * maxDimension;
              width = maxDimension;
            } else {
              width = (width / height) * maxDimension;
              height = maxDimension;
            }
          }
          
          canvas.width = width;
          canvas.height = height;
          
          const ctx = canvas.getContext('2d');
          ctx.drawImage(img, 0, 0, width, height);
          
          // Convertir a blob con calidad ajustable
          canvas.toBlob(
            (blob) => {
              if (blob.size <= maxSizeMB * 1024 * 1024) {
                resolve(blob);
              } else {
                // Si aún es muy grande, reducir calidad
                canvas.toBlob(
                  (blob2) => resolve(blob2),
                  'image/jpeg',
                  0.7
                );
              }
            },
            'image/jpeg',
            0.9
          );
        };
        img.onerror = reject;
        img.src = e.target.result;
      };
      
      reader.onerror = reject;
      reader.readAsDataURL(file);
    });
  };

  const handleFileSelect = async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    // Validar tipo
    if (!file.type.startsWith('image/')) {
      toast.error('Solo se permiten imágenes');
      return;
    }

    // Validar tamaño (15MB máximo)
    const maxSize = 15 * 1024 * 1024; // 15MB
    if (file.size > maxSize) {
      toast.error('La imagen no debe superar 15MB');
      return;
    }

    try {
      // Comprimir imagen si es necesaria
      const compressedBlob = await compressImage(file);
      const compressedFile = new File([compressedBlob], file.name, {
        type: 'image/jpeg',
        lastModified: Date.now(),
      });

      setSelectedImage(compressedFile);
      
      // Crear preview
      const reader = new FileReader();
      reader.onloadend = () => {
        setPreview(reader.result);
      };
      reader.readAsDataURL(compressedFile);

      console.log('[ProfilePicture] Imagen seleccionada:', {
        originalSize: (file.size / 1024 / 1024).toFixed(2) + 'MB',
        compressedSize: (compressedFile.size / 1024 / 1024).toFixed(2) + 'MB'
      });
    } catch (error) {
      console.error('[ProfilePicture] Error procesando imagen:', error);
      toast.error('Error al procesar la imagen');
    }
  };

  const handleUpload = async () => {
    if (!selectedImage) {
      toast.error('Selecciona una imagen primero');
      return;
    }

    setUploading(true);
    
    try {
      // Paso 1: Subir imagen al backend
      const formData = new FormData();
      formData.append('file', selectedImage);

      console.log('[ProfilePicture] Subiendo imagen...');
      
      const uploadResponse = await api.post('/api/upload-image', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });

      const imageUrl = uploadResponse.data.image_url;
      console.log('[ProfilePicture] Imagen subida:', imageUrl.substring(0, 50) + '...');

      // Paso 2: Actualizar foto de perfil del usuario
      console.log('[ProfilePicture] Actualizando perfil...');
      
      const updateResponse = await api.put('/api/auth/profile-picture', {
        picture_url: imageUrl
      });

      console.log('[ProfilePicture] Perfil actualizado exitosamente');

      // Actualizar usuario en el contexto
      if (onUpdate) {
        onUpdate(updateResponse.data);
      }

      toast.success('✅ Foto de perfil actualizada');
      
      // Limpiar y cerrar
      setSelectedImage(null);
      setPreview(null);
      onOpenChange(false);

    } catch (error) {
      console.error('[ProfilePicture] Error:', error);
      const errorMsg = error.response?.data?.detail || 'Error al actualizar la foto';
      toast.error(errorMsg);
    } finally {
      setUploading(false);
    }
  };

  const handleCancel = () => {
    setSelectedImage(null);
    setPreview(null);
    onOpenChange(false);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="bg-stone-950 border-stone-800 max-w-md">
        <DialogHeader>
          <DialogTitle className="text-white flex items-center gap-3">
            <Camera className="w-6 h-6 text-red-400" />
            Cambiar Foto de Perfil
          </DialogTitle>
        </DialogHeader>

        <div className="space-y-4">
          {/* Preview actual */}
          <div className="flex justify-center">
            <div className="relative">
              <img
                src={preview || user?.picture || '/default-avatar.png'}
                alt="Preview"
                className="w-40 h-40 rounded-full object-cover border-4 border-stone-800"
              />
              {uploading && (
                <div className="absolute inset-0 bg-black/60 rounded-full flex items-center justify-center">
                  <Loader2 className="w-8 h-8 text-white animate-spin" />
                </div>
              )}
            </div>
          </div>

          {/* Selector de archivo */}
          <div>
            <input
              ref={fileInputRef}
              type="file"
              accept="image/*"
              onChange={handleFileSelect}
              className="hidden"
            />
            
            <Button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              disabled={uploading}
              className="w-full bg-stone-800 hover:bg-stone-700 text-white"
            >
              <Upload className="w-4 h-4 mr-2" />
              {selectedImage ? 'Cambiar imagen' : 'Seleccionar imagen'}
            </Button>
          </div>

          {/* Info */}
          <div className="bg-stone-900/50 rounded-lg p-3">
            <p className="text-xs text-stone-400">
              📸 Formatos: JPG, PNG, GIF, WEBP
              <br />
              📦 Tamaño máximo: 15MB
              <br />
              ✨ La imagen se optimizará automáticamente
            </p>
          </div>

          {/* Botones */}
          <div className="flex gap-3">
            <Button
              type="button"
              variant="outline"
              onClick={handleCancel}
              disabled={uploading}
              className="flex-1 border-stone-700 text-stone-400 hover:bg-stone-800"
            >
              <X className="w-4 h-4 mr-2" />
              Cancelar
            </Button>
            
            <Button
              type="button"
              onClick={handleUpload}
              disabled={!selectedImage || uploading}
              className="flex-1 bg-red-600 hover:bg-red-700 text-white"
            >
              {uploading ? (
                <>
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  Subiendo...
                </>
              ) : (
                <>
                  <Camera className="w-4 h-4 mr-2" />
                  Guardar
                </>
              )}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
};

export default ProfilePictureEditor;
