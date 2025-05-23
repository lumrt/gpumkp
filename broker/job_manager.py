#!/usr/bin/env python3
"""
Gestionnaire de jobs pour le broker.
"""
import json
import logging
import uuid
from datetime import datetime
from pathlib import Path
import threading

logger = logging.getLogger("job_manager")

class JobManager:
    """Gestionnaire de jobs pour le broker"""
    
    def __init__(self, db_path=None):
        """Initialise le gestionnaire de jobs"""
        self.db_path = db_path or Path("jobs_db.json")
        self.jobs = {}
        self.workers = {}
        self.lock = threading.Lock()
        
        # Charger les données existantes si le fichier existe
        self._load_data()
    
    def _load_data(self):
        """Charge les données depuis le fichier"""
        if self.db_path.exists():
            try:
                with open(self.db_path, 'r') as f:
                    data = json.load(f)
                    self.jobs = data.get('jobs', {})
                    self.workers = data.get('workers', {})
                logger.info(f"Données chargées: {len(self.jobs)} jobs, {len(self.workers)} workers")
            except Exception as e:
                logger.error(f"Erreur lors du chargement des données: {str(e)}")
    
    def _save_data(self):
        """Sauvegarde les données dans le fichier"""
        try:
            with open(self.db_path, 'w') as f:
                json.dump({
                    'jobs': self.jobs,
                    'workers': self.workers
                }, f, indent=2)
            logger.info("Données sauvegardées")
        except Exception as e:
            logger.error(f"Erreur lors de la sauvegarde des données: {str(e)}")
    
    def register_worker(self, worker_address, gpu_info):
        """Enregistre un nouveau worker"""
        with self.lock:
            # Vérifier si le worker existe déjà
            for worker_id, worker in self.workers.items():
                if worker['address'] == worker_address:
                    logger.info(f"Worker déjà enregistré: {worker_id}")
                    return worker_id
            
            # Créer un nouvel ID pour le worker
            worker_id = str(uuid.uuid4())
            
            # Enregistrer le worker
            self.workers[worker_id] = {
                'id': worker_id,
                'address': worker_address,
                'gpu_info': gpu_info,
                'registered_at': datetime.utcnow().isoformat(),
                'last_seen': datetime.utcnow().isoformat(),
                'jobs_completed': 0
            }
            
            logger.info(f"Nouveau worker enregistré: {worker_id}")
            self._save_data()
            
            return worker_id
    
    def create_job(self, job_id, client_address, bundle_path):
        """Crée un nouveau job"""
        with self.lock:
            # Enregistrer le job
            self.jobs[job_id] = {
                'job_id': job_id,
                'client_address': client_address,
                'bundle_path': bundle_path,
                'status': 'pending',
                'created_at': datetime.utcnow().isoformat(),
                'updated_at': datetime.utcnow().isoformat()
            }
            
            logger.info(f"Nouveau job créé: {job_id}")
            self._save_data()
            
            return job_id
    
    def get_job(self, job_id):
        """Récupère un job par son ID"""
        return self.jobs.get(job_id)
    
    def get_jobs_for_worker(self, worker_id):
        """Récupère les jobs disponibles pour un worker"""
        with self.lock:
            # Mettre à jour la dernière activité du worker
            if worker_id in self.workers:
                self.workers[worker_id]['last_seen'] = datetime.utcnow().isoformat()
                self._save_data()
            
            # Récupérer les jobs en attente
            pending_jobs = []
            for job_id, job in self.jobs.items():
                if job['status'] == 'pending':
                    # Assigner le job au worker
                    job['status'] = 'assigned'
                    job['worker_id'] = worker_id
                    job['worker_address'] = self.workers[worker_id]['address']
                    job['assigned_at'] = datetime.utcnow().isoformat()
                    job['updated_at'] = datetime.utcnow().isoformat()
                    
                    pending_jobs.append(job)
                    logger.info(f"Job {job_id} assigné au worker {worker_id}")
                    
                    # Ne retourner qu'un seul job à la fois
                    break
            
            self._save_data()
            return pending_jobs
    
    def update_job_status(self, job_id, status, worker_id=None, error=None):
        """Met à jour le statut d'un job"""
        with self.lock:
            if job_id not in self.jobs:
                logger.error(f"Job {job_id} non trouvé")
                return False
            
            job = self.jobs[job_id]
            
            # Vérifier que le worker est autorisé à mettre à jour le job
            if worker_id and job.get('worker_id') != worker_id:
                logger.error(f"Worker {worker_id} non autorisé à mettre à jour le job {job_id}")
                return False
            
            # Mettre à jour le statut
            job['status'] = status
            job['updated_at'] = datetime.utcnow().isoformat()
            
            if status == 'completed' and worker_id and worker_id in self.workers:
                self.workers[worker_id]['jobs_completed'] += 1
            
            if error:
                job['error'] = error
            
            logger.info(f"Statut du job {job_id} mis à jour: {status}")
            self._save_data()
            
            return True
    
    def update_job_result(self, job_id, result_path, proof):
        """Met à jour le résultat d'un job"""
        with self.lock:
            if job_id not in self.jobs:
                logger.error(f"Job {job_id} non trouvé")
                return False
            
            job = self.jobs[job_id]
            
            # Mettre à jour le résultat
            job['result_path'] = result_path
            job['proof'] = proof
            job['updated_at'] = datetime.utcnow().isoformat()
            
            logger.info(f"Résultat du job {job_id} mis à jour")
            self._save_data()
            
            return True