#!/usr/bin/env python3
"""
Module pour créer des bundles de job à soumettre.
"""
import os
import tarfile
import tempfile
import logging
from pathlib import Path
import shutil

logger = logging.getLogger("job_creator")

def create_job_bundle(train_script_path, requirements_path, model_path=None, data_path=None, output_path=None):
    """
    Crée un bundle de job (.tar.gz) contenant le script d'entraînement, les requirements,
    le modèle (optionnel) et les données (optionnel).
    
    Args:
        train_script_path: Chemin vers le script d'entraînement
        requirements_path: Chemin vers le fichier requirements.txt
        model_path: Chemin vers le fichier du modèle (optionnel)
        data_path: Chemin vers le répertoire de données (optionnel)
        output_path: Chemin de sortie pour le bundle (optionnel)
        
    Returns:
        Le chemin vers le bundle créé
    """
    logger.info(f"Création d'un bundle de job avec {train_script_path} et {requirements_path}")
    
    # Créer un répertoire temporaire
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_dir_path = Path(temp_dir)
        
        # Copier les fichiers dans le répertoire temporaire
        shutil.copy(train_script_path, temp_dir_path / "train.py")
        shutil.copy(requirements_path, temp_dir_path / "requirements.txt")
        
        # Copier le modèle s'il est fourni
        if model_path and os.path.exists(model_path):
            model_filename = os.path.basename(model_path)
            shutil.copy(model_path, temp_dir_path / model_filename)
            logger.info(f"Modèle {model_filename} ajouté au bundle.")
        elif model_path:
            logger.warning(f"Chemin du modèle {model_path} spécifié mais non trouvé. Il ne sera pas inclus.")

        # Copier les données si le chemin est fourni et est un répertoire
        if data_path and os.path.isdir(data_path):
            data_dir_name = os.path.basename(data_path)
            shutil.copytree(data_path, temp_dir_path / data_dir_name)
            logger.info(f"Répertoire de données {data_dir_name} ajouté au bundle.")
        elif data_path:
            logger.warning(f"Chemin des données {data_path} spécifié mais n'est pas un répertoire valide ou n'existe pas. Il ne sera pas inclus.")

        # Créer le bundle
        if not output_path:
            output_path = f"job_bundle_{os.path.basename(train_script_path).split('.')[0]}.tar.gz"
        
        with tarfile.open(output_path, "w:gz") as tar:
            tar.add(temp_dir, arcname="job")
        
        logger.info(f"Bundle créé: {output_path}")
        
        return output_path

def extract_job_bundle(bundle_path, extract_dir):
    """
    Extrait un bundle de job dans un répertoire.
    
    Args:
        bundle_path: Chemin vers le bundle à extraire
        extract_dir: Répertoire d'extraction
        
    Returns:
        Le chemin vers le répertoire contenant les fichiers extraits
    """
    logger.info(f"Extraction du bundle {bundle_path} vers {extract_dir}")
    
    # Créer le répertoire d'extraction s'il n'existe pas
    os.makedirs(extract_dir, exist_ok=True)
    
    # Extraire le bundle
    with tarfile.open(bundle_path, "r:gz") as tar:
        tar.extractall(path=extract_dir)
    
    job_dir = Path(extract_dir) / "job"
    logger.info(f"Bundle extrait dans {job_dir}")
    
    return job_dir