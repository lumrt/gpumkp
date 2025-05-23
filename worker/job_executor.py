#!/usr/bin/env python3
"""
Module pour exécuter des jobs dans des conteneurs Docker.
"""
import os
import logging
import subprocess
import tempfile
from pathlib import Path

from client.job_creator import extract_job_bundle

logger = logging.getLogger("job_executor")

def execute_job(job_bundle_path, work_dir):
    """
    Exécute un job dans un conteneur Docker.
    
    Args:
        job_bundle_path: Chemin vers le bundle de job
        work_dir: Répertoire de travail
        
    Returns:
        Le chemin vers le répertoire contenant les résultats
    """
    logger.info(f"Exécution du job {job_bundle_path}")
    
    # Extraire le bundle
    job_dir = extract_job_bundle(job_bundle_path, work_dir)
    
    # Créer un répertoire pour les résultats
    result_dir = Path(work_dir) / "result"
    os.makedirs(result_dir, exist_ok=True)
    
    # Créer un Dockerfile
    dockerfile_path = create_dockerfile(job_dir)
    
    # Construire l'image Docker
    image_name = f"gpu-job-{os.path.basename(job_bundle_path).split('.')[0]}"
    build_docker_image(dockerfile_path, image_name)
    
    # Exécuter le conteneur
    run_docker_container(image_name, result_dir)
    
    logger.info(f"Job exécuté avec succès. Résultats dans {result_dir}")
    return result_dir

def create_dockerfile(job_dir):
    """Crée un Dockerfile pour le job"""
    logger.info("Création du Dockerfile")
    
    dockerfile_path = Path(job_dir) / "Dockerfile"
    
    with open(dockerfile_path, 'w') as f:
        f.write("""FROM pytorch/pytorch:2.0.1-cuda11.7-cudnn8-runtime

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "train.py"]
""")
    
    logger.info(f"Dockerfile créé: {dockerfile_path}")
    return dockerfile_path

def build_docker_image(dockerfile_path, image_name):
    """Construit une image Docker"""
    logger.info(f"Construction de l'image Docker {image_name}")
    
    dockerfile_dir = os.path.dirname(dockerfile_path)
    
    try:
        subprocess.run(
            ["docker", "build", "-t", image_name, "."],
            check=True,
            cwd=dockerfile_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        logger.info(f"Image Docker construite: {image_name}")
    except subprocess.CalledProcessError as e:
        logger.error(f"Erreur lors de la construction de l'image Docker: {e.stderr.decode()}")
        raise

def run_docker_container(image_name, result_dir):
    """Exécute un conteneur Docker"""
    logger.info(f"Exécution du conteneur Docker {image_name}")
    
    try:
        # Essayer d'abord avec le support GPU
        try:
            subprocess.run(
                [
                    "docker", "run", "--rm",
                    "--gpus", "all",
                    "-v", f"{result_dir}:/app/output",
                    "-e", "OUTPUT_DIR=/app/output",
                    image_name
                ],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            logger.info("Conteneur exécuté avec support GPU")
        except subprocess.CalledProcessError:
            # Si le support GPU échoue, essayer sans GPU
            logger.warning("Échec de l'exécution avec GPU, tentative sans GPU")
            subprocess.run(
                [
                    "docker", "run", "--rm",
                    "-v", f"{result_dir}:/app/output",
                    "-e", "OUTPUT_DIR=/app/output",
                    image_name
                ],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            logger.info("Conteneur exécuté sans support GPU")
        
        # La commande de copie du modèle est supprimée car le modèle est maintenant sauvegardé directement dans le volume monté
        logger.info(f"Vérification des fichiers dans le répertoire résultat: {result_dir}")
        try:
            files = os.listdir(result_dir)
            logger.info(f"Fichiers disponibles dans {result_dir}: {files}")
        except Exception as e:
            logger.error(f"Erreur lors de la liste des fichiers: {str(e)}")
        
    except subprocess.CalledProcessError as e:
        logger.error(f"Erreur lors de l'exécution du conteneur Docker: {e.stderr.decode() if hasattr(e, 'stderr') else str(e)}")
        raise