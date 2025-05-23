#!/usr/bin/env python3
"""
Worker pour exécuter des jobs GPU.
Le worker est responsable de :
1. S'enregistrer auprès du broker
2. Récupérer des jobs à exécuter
3. Exécuter les jobs sur les GPUs disponibles
4. Générer des preuves de travail
5. Soumettre les résultats au broker
"""
import os
import sys
import time
import json
import logging
import argparse
import requests
import tempfile
from pathlib import Path

from worker.job_executor import execute_job
from worker.proof_generator import generate_proof
from xrpl_utils.wallet import load_wallet_from_file

# Configuration du système de logging
# Les logs sont écrits dans worker.log et la console
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("worker.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("worker")

# Configuration du worker
BROKER_URL = "http://localhost:8000"  # URL du broker
POLL_INTERVAL = 10  # Intervalle de polling en secondes

def register_worker(wallet_file):
    """
    Enregistre le worker auprès du broker
    Args:
        wallet_file: Chemin vers le fichier wallet XRPL
    Returns:
        worker_id: Identifiant unique du worker
    """
    logger.info("Enregistrement du worker auprès du broker")
    
    # Chargement du wallet XRPL
    wallet = load_wallet_from_file(wallet_file)
    worker_address = wallet.classic_address
    
    # Enregistrement auprès du broker
    response = requests.post(
        f"{BROKER_URL}/workers/register",
        json={
            "worker_address": worker_address,
            "gpu_info": get_gpu_info()
        }
    )
    
    if response.status_code == 200:
        worker_id = response.json().get('worker_id')
        logger.info(f"Worker enregistré avec succès. ID: {worker_id}")
        return worker_id
    else:
        logger.error(f"Erreur lors de l'enregistrement du worker: {response.text}")
        return None

def get_gpu_info():
    """
    Récupère les informations sur les GPUs disponibles
    Returns:
        dict: Informations sur les GPUs (disponibilité, nombre, noms)
    """
    try:
        import torch
        gpu_info = {
            "cuda_available": torch.cuda.is_available(),
            "device_count": torch.cuda.device_count() if torch.cuda.is_available() else 0,
            "device_names": [torch.cuda.get_device_name(i) for i in range(torch.cuda.device_count())] if torch.cuda.is_available() else []
        }
    except ImportError:
        gpu_info = {
            "cuda_available": False,
            "device_count": 0,
            "device_names": []
        }
    
    return gpu_info

def poll_for_jobs(worker_id, wallet_file):
    """
    Interroge le broker pour obtenir des jobs à exécuter
    Args:
        worker_id: Identifiant du worker
        wallet_file: Chemin vers le fichier wallet
    """
    logger.info(f"Recherche de jobs pour le worker {worker_id}")
    
    response = requests.get(f"{BROKER_URL}/workers/{worker_id}/jobs")
    
    if response.status_code == 200:
        jobs = response.json().get('jobs', [])
        if jobs:
            logger.info(f"Jobs disponibles: {len(jobs)}")
            # Traitement du premier job disponible
            job = jobs[0]
            process_job(job, worker_id, wallet_file)
        else:
            logger.info("Aucun job disponible")
    else:
        logger.error(f"Erreur lors de la recherche de jobs: {response.text}")

def download_job(job_id):
    """Télécharge un job depuis le broker"""
    logger.info(f"Téléchargement du job {job_id}")
    
    response = requests.get(f"{BROKER_URL}/jobs/{job_id}/download", stream=True)
    
    if response.status_code == 200:
        # Créer un fichier temporaire pour stocker le job
        fd, temp_path = tempfile.mkstemp(suffix='.tar.gz')
        os.close(fd)
        
        with open(temp_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        logger.info(f"Job téléchargé: {temp_path}")
        return temp_path
    else:
        logger.error(f"Erreur lors du téléchargement du job: {response.text}")
        return None

def process_job(job, worker_id, wallet_file):
    """
    Traite un job complet
    Args:
        job: Informations sur le job
        worker_id: Identifiant du worker
        wallet_file: Chemin vers le fichier wallet
    """
    job_id = job['job_id']
    logger.info(f"Traitement du job {job_id}")
    
    # Mise à jour du statut du job
    update_job_status(job_id, worker_id, "processing")
    
    try:
        # Téléchargement du job
        job_path = download_job(job_id)
        if not job_path:
            raise Exception("Impossible de télécharger le job")
        
        # Exécution du job dans un répertoire temporaire
        with tempfile.TemporaryDirectory() as temp_dir:
            # Exécution du job
            result_dir = execute_job(job_path, temp_dir)
            
            # Génération de la preuve d'exécution
            model_path = os.path.join(result_dir, "model.pt")
            if not os.path.exists(model_path):
                raise Exception("Le modèle n'a pas été généré")
            
            proof = generate_proof(model_path, load_wallet_from_file(wallet_file))
            
            # Création et soumission du bundle de résultats
            result_bundle = create_result_bundle(result_dir, proof)
            submit_result(job_id, worker_id, result_bundle, proof)
            
            # Nettoyage des fichiers temporaires
            os.unlink(job_path)
            os.unlink(result_bundle)
        
        logger.info(f"Job {job_id} traité avec succès")
    
    except Exception as e:
        logger.error(f"Erreur lors du traitement du job {job_id}: {str(e)}")
        update_job_status(job_id, worker_id, "failed", error=str(e))

def create_result_bundle(result_dir, proof):
    """Crée un bundle de résultats"""
    logger.info("Création du bundle de résultats")
    
    # Créer un fichier temporaire pour le bundle
    fd, temp_path = tempfile.mkstemp(suffix='.tar.gz')
    os.close(fd)
    
    # Sauvegarder la preuve dans un fichier
    proof_path = os.path.join(result_dir, "proof.json")
    with open(proof_path, 'w') as f:
        json.dump(proof, f)
    
    # Créer le bundle
    import tarfile
    with tarfile.open(temp_path, "w:gz") as tar:
        tar.add(result_dir, arcname="result")
    
    logger.info(f"Bundle de résultats créé: {temp_path}")
    return temp_path

def update_job_status(job_id, worker_id, status, error=None):
    """Met à jour le statut d'un job"""
    logger.info(f"Mise à jour du statut du job {job_id}: {status}")
    
    data = {
        "status": status,
        "worker_id": worker_id
    }
    
    if error:
        data["error"] = error
    
    response = requests.put(f"{BROKER_URL}/jobs/{job_id}/status", json=data)
    
    if response.status_code != 200:
        logger.error(f"Erreur lors de la mise à jour du statut: {response.text}")

def submit_result(job_id, worker_id, result_bundle, proof):
    """Soumet le résultat d'un job au broker"""
    logger.info(f"Soumission du résultat du job {job_id}")
    
    with open(result_bundle, 'rb') as f:
        files = {'result_bundle': f}
        data = {
            'worker_id': worker_id,
            'proof': json.dumps(proof)
        }
        
        response = requests.post(f"{BROKER_URL}/jobs/{job_id}/result", files=files, data=data)
    
    if response.status_code == 200:
        logger.info(f"Résultat soumis avec succès")
        update_job_status(job_id, worker_id, "completed")
    else:
        logger.error(f"Erreur lors de la soumission du résultat: {response.text}")
        update_job_status(job_id, worker_id, "failed", error="Erreur lors de la soumission du résultat")

def main():
    """
    Point d'entrée principal du worker
    Le worker :
    1. S'enregistre auprès du broker
    2. Poll régulièrement pour de nouveaux jobs
    3. Exécute les jobs reçus
    """
    parser = argparse.ArgumentParser(description="Worker pour exécuter des jobs GPU")
    parser.add_argument("--wallet", required=True, help="Chemin vers le fichier wallet")
    args = parser.parse_args()
    
    # Enregistrement du worker
    worker_id = register_worker(args.wallet)
    if not worker_id:
        logger.error("Impossible d'enregistrer le worker")
        return 1
    
    # Boucle principale de polling
    try:
        while True:
            poll_for_jobs(worker_id, args.wallet)
            time.sleep(POLL_INTERVAL)
    except KeyboardInterrupt:
        logger.info("Arrêt du worker")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())