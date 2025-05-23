#!/usr/bin/env python3
"""
API REST du broker pour coordonner les jobs et les workers.
Le broker est le composant central qui :
1. Gère l'enregistrement des workers
2. Distribue les jobs aux workers
3. Valide les preuves de travail
4. Gère les paiements
5. Stocke les résultats
"""
import os
import sys
import uuid
import json
import logging
import tempfile
from pathlib import Path
from datetime import datetime

from fastapi import FastAPI, File, UploadFile, Form, HTTPException, BackgroundTasks, Body
from fastapi.responses import JSONResponse, FileResponse
import uvicorn
from pydantic import BaseModel

from broker.job_manager import JobManager
from broker.proof_validator import validate_proof
from broker.payment_handler import process_payment
from xrpl_utils.wallet import load_wallet_from_file

# Configuration du système de logging
# Les logs sont écrits dans broker.log et la console
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("broker.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("broker")

# Initialisation de l'API FastAPI
app = FastAPI(title="GPU Marketplace Broker")

# Modèle Pydantic pour l'enregistrement du worker
class WorkerRegistrationRequest(BaseModel):
    worker_address: str
    gpu_info: dict

# Initialisation du gestionnaire de jobs
job_manager = JobManager()

# Configuration des répertoires de stockage
STORAGE_DIR = Path("storage")
JOBS_DIR = STORAGE_DIR / "jobs"  # Stockage des jobs soumis
RESULTS_DIR = STORAGE_DIR / "results"  # Stockage des résultats

# Création des répertoires de stockage
JOBS_DIR.mkdir(parents=True, exist_ok=True)
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

# Chargement du wallet du broker pour les transactions XRPL
BROKER_WALLET = None
if os.path.exists("broker_wallet.json"):
    BROKER_WALLET = load_wallet_from_file("broker_wallet.json")

@app.on_event("startup")
async def startup_event():
    """Événement déclenché au démarrage du broker"""
    logger.info("Démarrage du broker")

@app.on_event("shutdown")
async def shutdown_event():
    """Événement déclenché à l'arrêt du broker"""
    logger.info("Arrêt du broker")

@app.get("/")
async def root():
    """Endpoint de base pour vérifier que l'API est fonctionnelle"""
    return {"message": "GPU Marketplace Broker API"}

@app.post("/workers/register")
async def register_worker(request: WorkerRegistrationRequest = Body(...)):
    """
    Enregistre un nouveau worker dans le système
    Args:
        request: Données d'enregistrement du worker (adresse XRPL, informations GPU)
    """
    try:
        # Utiliser directement les champs de l'objet request
        worker_id = job_manager.register_worker(request.worker_address, request.gpu_info)
        return {"worker_id": worker_id}
    except Exception as e:
        logger.error(f"Erreur lors de l'enregistrement du worker: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/workers/{worker_id}/jobs")
async def get_worker_jobs(worker_id: str):
    """Récupère les jobs disponibles pour un worker"""
    try:
        jobs = job_manager.get_jobs_for_worker(worker_id)
        return {"jobs": jobs}
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des jobs: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/jobs")
async def create_job(job_bundle: UploadFile = File(...), client_address: str = Form(...)):
    """Crée un nouveau job"""
    try:
        # Générer un ID unique pour le job
        job_id = str(uuid.uuid4())
        
        # Sauvegarder le bundle
        job_path = JOBS_DIR / f"{job_id}.tar.gz"
        with open(job_path, "wb") as f:
            f.write(await job_bundle.read())
        
        # Enregistrer le job
        job_manager.create_job(job_id, client_address, str(job_path))
        
        return {"job_id": job_id}
    except Exception as e:
        logger.error(f"Erreur lors de la création du job: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/jobs/{job_id}")
async def get_job_status(job_id: str):
    """Récupère le statut d'un job"""
    try:
        job = job_manager.get_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job non trouvé")
        return job
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur lors de la récupération du statut: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/jobs/{job_id}/status")
async def update_job_status(job_id: str, status: dict):
    """Met à jour le statut d'un job"""
    try:
        job_manager.update_job_status(job_id, status["status"], status.get("worker_id"), status.get("error"))
        return {"status": "updated"}
    except Exception as e:
        logger.error(f"Erreur lors de la mise à jour du statut: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/jobs/{job_id}/download")
async def download_job(job_id: str):
    """Télécharge un job"""
    try:
        job = job_manager.get_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job non trouvé")
        
        job_path = Path(job["bundle_path"])
        if not job_path.exists():
            raise HTTPException(status_code=404, detail="Bundle de job non trouvé")
        
        return FileResponse(job_path, media_type="application/gzip", filename=f"job_{job_id}.tar.gz")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur lors du téléchargement du job: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/jobs/{job_id}/result")
async def submit_job_result(
    job_id: str,
    background_tasks: BackgroundTasks,
    result_bundle: UploadFile = File(...),
    worker_id: str = Form(...),
    proof: str = Form(...)
):
    """
    Soumet le résultat d'un job terminé
    Ce endpoint :
    1. Vérifie l'authenticité du worker
    2. Valide la preuve de travail
    3. Sauvegarde les résultats
    4. Déclenche le paiement en arrière-plan
    """
    try:
        # Vérification de l'existence du job
        job = job_manager.get_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job non trouvé")
        
        # Vérification de l'autorisation du worker
        if job.get("worker_id") != worker_id:
            raise HTTPException(status_code=403, detail="Worker non autorisé")
        
        # Sauvegarde du bundle de résultats
        result_path = RESULTS_DIR / f"{job_id}.tar.gz"
        with open(result_path, "wb") as f:
            f.write(await result_bundle.read())
        
        # Validation de la preuve de travail
        proof_dict = json.loads(proof)
        is_valid = validate_proof(proof_dict, worker_id)
        
        if not is_valid:
            raise HTTPException(status_code=400, detail="Preuve invalide")
        
        # Mise à jour du job avec le résultat
        job_manager.update_job_result(job_id, str(result_path), proof_dict)
        
        # Traitement du paiement en arrière-plan
        background_tasks.add_task(
            process_payment,
            job["client_address"],
            job["worker_address"],
            job_id,
            BROKER_WALLET
        )
        
        return {"status": "success"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur lors de la soumission du résultat: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/jobs/{job_id}/result")
async def get_job_result(job_id: str):
    """Récupère le résultat d'un job"""
    try:
        job = job_manager.get_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job non trouvé")
        
        if job["status"] != "completed":
            raise HTTPException(status_code=400, detail="Le job n'est pas terminé")
        
        if not job.get("result_path"):
            raise HTTPException(status_code=404, detail="Résultat non trouvé")
        
        result_path = Path(job["result_path"])
        if not result_path.exists():
            raise HTTPException(status_code=404, detail="Fichier de résultat non trouvé")
        
        return FileResponse(result_path, media_type="application/gzip", filename=f"result_{job_id}.tar.gz")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur lors de la récupération du résultat: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

def main():
    """
    Point d'entrée principal pour démarrer le serveur
    Le serveur écoute sur le port 8000 et accepte les connexions de n'importe quelle interface
    """
    uvicorn.run("broker.api:app", host="0.0.0.0", port=8000, reload=True)

if __name__ == "__main__":
    main()