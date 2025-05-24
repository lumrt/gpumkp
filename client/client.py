#!/usr/bin/env python3
"""
Client pour soumettre des jobs à la plateforme.
"""
import os
import sys
import json
import time
import logging
import argparse
import requests
from pathlib import Path

from client.job_creator import create_job_bundle
from xrpl_utils.wallet import load_wallet_from_file

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("client.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("client")

BROKER_URL = "http://localhost:8000"

def submit_job(job_path, wallet_file):
    """Soumet un job au broker"""
    logger.info(f"Soumission du job {job_path} au broker")
    
    # Charger le wallet
    wallet = load_wallet_from_file(wallet_file)
    client_address = wallet.classic_address
    
    # Préparer les fichiers pour l'upload
    with open(job_path, 'rb') as f:
        files = {'job_bundle': f}
        data = {'client_address': client_address}
        
        # Soumettre le job au broker
        response = requests.post(f"{BROKER_URL}/jobs", files=files, data=data)
    
    if response.status_code == 200:
        job_id = response.json().get('job_id')
        logger.info(f"Job soumis avec succès. ID: {job_id}")
        return job_id
    else:
        logger.error(f"Erreur lors de la soumission du job: {response.text}")
        return None

def check_job_status(job_id):
    """Vérifie le statut d'un job"""
    logger.info(f"Vérification du statut du job {job_id}")
    
    response = requests.get(f"{BROKER_URL}/jobs/{job_id}")
    
    if response.status_code == 200:
        status = response.json()
        logger.info(f"Statut du job: {status}")
        return status
    else:
        logger.error(f"Erreur lors de la vérification du statut: {response.text}")
        return None

def download_result(job_id, output_dir):
    """Télécharge le résultat d'un job"""
    logger.info(f"Téléchargement du résultat du job {job_id}")
    
    response = requests.get(f"{BROKER_URL}/jobs/{job_id}/result", stream=True)
    
    if response.status_code == 200:
        output_path = Path(output_dir) / f"result_{job_id}.tar.gz"
        with open(output_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        logger.info(f"Résultat téléchargé: {output_path}")
        return output_path
    else:
        logger.error(f"Erreur lors du téléchargement du résultat: {response.text}")
        return None

def main():
    parser = argparse.ArgumentParser(description="Client pour soumettre des jobs GPU")
    parser.add_argument("--wallet", required=True, help="Chemin vers le fichier wallet")
    parser.add_argument("--train-script", default="client/example/train.py", help="Script d'entraînement")
    parser.add_argument("--model-path", help="Chemin vers le fichier du modèle (optionnel)")
    parser.add_argument("--data-path", help="Chemin vers le répertoire de données (optionnel)")
    parser.add_argument("--requirements", default="client/example/requirements.txt", help="Fichier requirements.txt")
    parser.add_argument("--output-dir", default="./output", help="Répertoire de sortie pour les résultats")
    args = parser.parse_args()
    
    # Créer le répertoire de sortie s'il n'existe pas
    os.makedirs(args.output_dir, exist_ok=True)
    
    # Créer le bundle de job
    job_bundle_path = create_job_bundle(args.train_script, args.requirements, args.model_path, args.data_path)
    
    # Soumettre le job
    job_id = submit_job(job_bundle_path, args.wallet)
    if not job_id:
        logger.error("Échec de la soumission du job")
        return
    
    # Vérifier le statut du job jusqu'à ce qu'il soit terminé
    status = None
    while status != "completed" and status != "failed":
        time.sleep(5)
        job_status = check_job_status(job_id)
        if job_status:
            status = job_status.get('status')
    
    # Si le job est terminé avec succès, télécharger le résultat
    if status == "completed":
        result_path = download_result(job_id, args.output_dir)
        if result_path:
            logger.info(f"Job terminé avec succès. Résultat: {result_path}")
            return 0
    
    logger.error("Le job a échoué ou n'a pas pu être complété")
    return 1

if __name__ == "__main__":
    sys.exit(main())