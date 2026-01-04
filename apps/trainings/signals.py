"""
Signals para o app de treinamentos.
Inclui processamento automático de vídeos (duração e thumbnail).
"""

import os
import logging
from io import BytesIO
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.files.base import ContentFile
from django.conf import settings

from .models import UserProgress, Video

logger = logging.getLogger(__name__)


@receiver(post_save, sender=UserProgress)
def check_training_completion(sender, instance, created, **kwargs):
    """
    Verifica se o treinamento foi completado após salvar progresso.
    """
    if instance.completed:
        instance._check_training_completion()


@receiver(post_save, sender=Video)
def process_video_metadata(sender, instance, created, **kwargs):
    """
    Processa metadados do vídeo após upload.
    - Extrai duração do vídeo usando moviepy
    - Gera thumbnail do primeiro frame
    
    Só executa se:
    1. É um novo vídeo (created=True)
    2. Tem arquivo de vídeo
    3. Duração ainda não foi definida
    """
    if not created or not instance.video_file:
        return
    
    # Evita loop infinito - só processa se duração não foi definida
    if instance.duration_seconds > 0:
        return
    
    try:
        _extract_video_metadata(instance)
    except Exception as e:
        logger.error(f"Erro ao processar vídeo {instance.id}: {str(e)}")


def _extract_video_metadata(video_instance):
    """
    Extrai metadados do vídeo usando moviepy.
    Função separada para facilitar testes e manutenção.
    """
    try:
        from moviepy.editor import VideoFileClip
    except ImportError:
        logger.warning("moviepy não instalado. Pulando extração de metadados.")
        return
    
    video_path = None
    clip = None
    
    try:
        # Obtém o caminho do arquivo
        if hasattr(video_instance.video_file, 'path'):
            video_path = video_instance.video_file.path
        else:
            # Para storage remoto (GCS), baixa temporariamente
            logger.info(f"Vídeo em storage remoto, pulando processamento local")
            return
        
        if not os.path.exists(video_path):
            logger.warning(f"Arquivo de vídeo não encontrado: {video_path}")
            return
        
        # Abre o vídeo
        clip = VideoFileClip(video_path)
        
        # Extrai duração (em segundos)
        duration = int(clip.duration)
        
        # Gera thumbnail do primeiro frame (1 segundo)
        thumbnail_generated = False
        if not video_instance.thumbnail:
            try:
                # Pega frame em 1 segundo ou no início se vídeo for muito curto
                frame_time = min(1, clip.duration / 2)
                frame = clip.get_frame(frame_time)
                
                # Converte para imagem PIL
                from PIL import Image
                img = Image.fromarray(frame)
                
                # Redimensiona para thumbnail (16:9)
                img.thumbnail((640, 360), Image.Resampling.LANCZOS)
                
                # Salva em buffer
                buffer = BytesIO()
                img.save(buffer, format='JPEG', quality=85)
                buffer.seek(0)
                
                # Salva como thumbnail
                thumbnail_name = f"thumb_{video_instance.id}.jpg"
                video_instance.thumbnail.save(
                    thumbnail_name,
                    ContentFile(buffer.read()),
                    save=False
                )
                thumbnail_generated = True
                logger.info(f"Thumbnail gerado para vídeo {video_instance.id}")
                
            except Exception as e:
                logger.error(f"Erro ao gerar thumbnail: {str(e)}")
        
        # Atualiza o modelo (sem disparar o signal novamente)
        Video.objects.filter(pk=video_instance.pk).update(
            duration_seconds=duration
        )
        
        # Se gerou thumbnail, salva também
        if thumbnail_generated:
            video_instance.save(update_fields=['thumbnail'])
        
        logger.info(f"Vídeo {video_instance.id} processado: {duration}s")
        
    except Exception as e:
        logger.error(f"Erro ao processar vídeo: {str(e)}")
        raise
    
    finally:
        # Sempre fecha o clip para liberar recursos
        if clip:
            try:
                clip.close()
            except Exception:
                pass
