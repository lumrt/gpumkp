#!/usr/bin/env python3
"""
Script principal pour démontrer le fonctionnement complet de la plateforme.
Ce script orchestre l'ensemble du système en :
1. Configurant l'environnement
2. Créant les wallets XRPL
3. Démarant le broker et le worker
4. Exécutant un job client
5. Nettoyant les ressources
"""
import os
import time
import logging
import argparse
import subprocess
from pathlib import Path

# Configuration du système de logging pour suivre l'exécution
# Les logs sont écrits à la fois dans un fichier et dans la console
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("demo.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("demo")

def setup_environment():
    """
    Prépare l'environnement pour la démo en vérifiant :
    - La présence de Docker
    - La configuration de NVIDIA Docker pour l'accès GPU
    """
    logger.info("Configuration de l'environnement...")
    
    # Vérification de l'installation de Docker
    try:
        subprocess.run(["docker", "--version"], check=True, capture_output=True)
        logger.info("Docker est installé")
    except (subprocess.SubprocessError, FileNotFoundError):
        logger.error("Docker n'est pas installé ou n'est pas accessible")
        return False
    
    # Vérification de la configuration NVIDIA Docker
    try:
        result = subprocess.run(["docker", "run", "--rm", "--gpus", "all", "nvidia/cuda:11.0-base", "nvidia-smi"], 
                               check=True, capture_output=True)
        logger.info("NVIDIA Docker est configuré correctement")
    except subprocess.SubprocessError:
        logger.warning("NVIDIA Docker n'est pas configuré correctement. Le worker fonctionnera en mode CPU.")
    
    return True

def setup_xrpl_wallets():
    """Configure les wallets XRPL pour la démo"""
    from xrpl_utils.testnet_setup import create_funded_wallet
    from xrpl_utils.wallet import save_wallet_to_file
    
    logger.info("Création des wallets XRPL sur le testnet...")
    
    # Créer et financer les wallets
    client_wallet = create_funded_wallet("Client")
    worker_wallet = create_funded_wallet("Worker")
    broker_wallet = create_funded_wallet("Broker")
    
    # Sauvegarder les wallets
    save_wallet_to_file(client_wallet, "client_wallet.json")
    save_wallet_to_file(worker_wallet, "worker_wallet.json")
    save_wallet_to_file(broker_wallet, "broker_wallet.json")
    
    logger.info(f"Client wallet: {client_wallet.classic_address}")
    logger.info(f"Worker wallet: {worker_wallet.classic_address}")
    logger.info(f"Broker wallet: {broker_wallet.classic_address}")
    
    return client_wallet, worker_wallet, broker_wallet

def start_broker():
    """Démarre le broker en arrière-plan"""
    logger.info("Démarrage du broker...")
    broker_process = subprocess.Popen(
        ["uvicorn", "broker.api:app", "--host", "0.0.0.0", "--port", "8000"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    # Attendre que le broker soit prêt
    time.sleep(3)
    return broker_process

def start_worker(worker_wallet_path):
    """Démarre le worker en arrière-plan"""
    logger.info("Démarrage du worker...")
    worker_process = subprocess.Popen(
        ["python", "-m", "worker.worker", "--wallet", worker_wallet_path],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    # Attendre que le worker soit prêt
    time.sleep(2)
    return worker_process

def run_client_job(client_wallet_path):
    """Exécute un job client"""
    logger.info("Création et soumission d'un job client...")
    result = subprocess.run(
        ["python", "-m", "client.client", "--wallet", client_wallet_path],
        check=True,
        capture_output=True,
        text=True
    )
    logger.info(f"Résultat du job client: {result.stdout}")
    return result.stdout

def main():
    """
    Point d'entrée principal du script.
    Orchestre l'ensemble du processus de démonstration.
    """
    parser = argparse.ArgumentParser(description="Démo de la plateforme de location GPU")
    parser.add_argument("--skip-setup", action="store_true", help="Ignorer la configuration des wallets")
    args = parser.parse_args()
    
    logger.info("Démarrage de la démo de la plateforme de location GPU")
    
    # Vérification de l'environnement
    if not setup_environment():
        logger.error("Échec de la configuration de l'environnement")
        return
    
    # Configuration des wallets XRPL pour les paiements
    if not args.skip_setup:
        client_wallet, worker_wallet, broker_wallet = setup_xrpl_wallets()
        client_wallet_path = "client_wallet.json"
        worker_wallet_path = "worker_wallet.json"
    else:
        logger.info("Utilisation des wallets existants")
        client_wallet_path = "client_wallet.json"
        worker_wallet_path = "worker_wallet.json"
    
    # Démarrage des composants du système
    broker_process = start_broker()
    worker_process = start_worker(worker_wallet_path)
    
    try:
        # Exécution d'un job de test
        job_result = run_client_job(client_wallet_path)
        
        # Attente de la fin du traitement
        logger.info("Attente de la fin du job...")
        time.sleep(10)
        
        logger.info("Démo terminée avec succès!")
        
    finally:
        # Nettoyage des ressources
        logger.info("Arrêt des processus...")
        broker_process.terminate()
        worker_process.terminate()
        
        logger.info("Démo terminée")

if __name__ == "__main__":
    main()