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
    
    IMPORTANTE: Se o vídeo estiver em storage remoto (GCS/S3), 
    desativa a extração automática, pois MoviePy não consegue 
    ler o arquivo sem baixá-lo completamente, causando timeouts.
    
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
        # Verifica se o arquivo está em storage remoto
        # Storage remoto não tem atributo 'path', apenas 'url'
        if not hasattr(instance.video_file, 'path'):
            logger.info(f"Vídeo {instance.id} está em storage remoto. Pulando processamento local de metadados.")
            logger.info(f"Arquivo: {instance.video_file.name}, Storage: {instance.video_file.storage.__class__.__name__}")
            return
        
        # Verifica se o arquivo existe localmente
        video_path = instance.video_file.path
        if not os.path.exists(video_path):
            logger.warning(f"Arquivo de vídeo não encontrado localmente: {video_path}")
            logger.info(f"Pulando processamento de metadados para vídeo {instance.id}")
            return
        
        # Tenta processar metadados
        _extract_video_metadata(instance)
        
    except Exception as e:
        # Log detalhado mas não bloqueia o salvamento do vídeo
        logger.error(f"Erro ao processar metadados do vídeo {instance.id}: {str(e)}", exc_info=True)
        logger.info(f"Vídeo {instance.id} foi salvo com sucesso, mas processamento de metadados falhou.")
        # Não re-raise para não impedir o salvamento do vídeo


def _extract_video_metadata(video_instance):
    """
    Extrai metadados do vídeo usando moviepy.
    Função separada para facilitar testes e manutenção.
    
    IMPORTANTE: Esta função assume que o arquivo está disponível 
    localmente e que moviepy está instalado.
    """
    try:
        from moviepy.editor import VideoFileClip
    except ImportError:
        logger.warning("moviepy não instalado. Pulando extração de metadados.")
        return
    
    video_path = None
    clip = None
    
    try:
        # Obtém o caminho do arquivo (já verificado no signal)
        video_path = video_instance.video_file.path
        
        logger.info(f"Iniciando processamento de metadados para vídeo {video_instance.id}: {video_path}")
        
        # Abre o vídeo com timeout implícito (MoviePy tem limites internos)
        clip = VideoFileClip(video_path, verbose=False, logger=None)
        
        # Extrai duração (em segundos)
        duration = int(clip.duration)
        logger.info(f"Duração extraída: {duration}s")
        
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
                logger.error(f"Erro ao gerar thumbnail para vídeo {video_instance.id}: {str(e)}", exc_info=True)
        
        # Atualiza o modelo (sem disparar o signal novamente)
        Video.objects.filter(pk=video_instance.pk).update(
            duration_seconds=duration
        )
        
        # Se gerou thumbnail, salva também
        if thumbnail_generated:
            video_instance.save(update_fields=['thumbnail'])
        
        logger.info(f"✅ Vídeo {video_instance.id} processado com sucesso: {duration}s")
        
    except Exception as e:
        # Log detalhado do erro
        logger.error(f"❌ Erro ao processar metadados do vídeo {video_instance.id}: {str(e)}", exc_info=True)
        logger.error(f"Arquivo: {video_path}, Existe: {os.path.exists(video_path) if video_path else 'N/A'}")
        # Não re-raise para não bloquear o salvamento do vídeo
    
    finally:
        # Sempre fecha o clip para liberar recursos
        if clip:
            try:
                clip.close()
                logger.debug(f"Clip fechado para vídeo {video_instance.id}")
            except Exception as e:
                logger.warning(f"Erro ao fechar clip do vídeo {video_instance.id}: {str(e)}")
