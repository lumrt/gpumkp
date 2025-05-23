#!/usr/bin/env python3
"""
Module pour valider les preuves d'exécution.
"""
import logging

logger = logging.getLogger("proof_validator")

def validate_proof(proof, worker_id):
    """
    Valide une preuve d'exécution.
    
    Args:
        proof: Dictionnaire contenant la preuve
        worker_id: ID du worker qui a soumis la preuve
        
    Returns:
        True si la preuve est valide, False sinon
    """
    logger.info(f"Validation de la preuve pour le worker {worker_id}")
    
    # Vérifier que la preuve contient les champs requis
    required_fields = ['model_hash', 'timestamp', 'worker_address', 'signature']
    for field in required_fields:
        if field not in proof:
            logger.error(f"Champ manquant dans la preuve: {field}")
            return False
    
    # Vérifier la signature
    # Dans une implémentation réelle, cela vérifierait cryptographiquement la signature
    # Pour cette démo, nous simulons la vérification
    from xrpl_utils.wallet import verify_signature
    
    is_valid = verify_signature(
        proof['model_hash'],
        proof['signature'],
        proof['worker_address']
    )
    
    if is_valid:
        logger.info("Preuve validée avec succès")
    else:
        logger.error("Signature invalide")
    
    return is_valid