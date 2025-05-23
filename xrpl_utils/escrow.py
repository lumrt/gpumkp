#!/usr/bin/env python3
"""
Utilitaires pour gérer les escrows XRPL.
"""
import logging
from datetime import datetime, timedelta

logger = logging.getLogger("xrpl_escrow")

try:
    import xrpl
    from xrpl.models.transactions import EscrowCreate, EscrowFinish
    from xrpl.wallet import Wallet
    from xrpl.clients import JsonRpcClient
    from xrpl.transaction import submit_and_wait
    XRPL_AVAILABLE = True
except ImportError:
    logger.warning("xrpl-py non disponible, utilisation d'escrows simulés")
    XRPL_AVAILABLE = False

# URL du serveur XRPL Testnet
TESTNET_URL = "https://s.altnet.rippletest.net:51234"

def create_escrow(sender_wallet, destination_address, amount_xrp, job_id, finish_after=3600):
    """
    Crée un escrow XRPL.
    
    Args:
        sender_wallet: Wallet XRPL de l'expéditeur
        destination_address: Adresse XRPL du destinataire
        amount_xrp: Montant en XRP à mettre en escrow
        job_id: ID du job associé
        finish_after: Délai en secondes avant que l'escrow puisse être terminé
        
    Returns:
        Hash de la transaction et séquence de l'escrow
    """
    logger.info(f"Création d'un escrow de {amount_xrp} XRP pour {destination_address}")
    
    if XRPL_AVAILABLE and isinstance(sender_wallet, Wallet):
        # Convertir le montant en drops (1 XRP = 1,000,000 drops)
        amount_drops = int(amount_xrp * 1_000_000)
        
        # Calculer la date de fin
        finish_after_date = datetime.utcnow() + timedelta(seconds=finish_after)
        
        # Créer le client XRPL
        client = JsonRpcClient(TESTNET_URL)
        
        # Créer la transaction d'escrow
        escrow_create = EscrowCreate(
            account=sender_wallet.classic_address,
            destination=destination_address,
            amount=str(amount_drops),
            finish_after=int(finish_after_date.timestamp())
        )
        
        # Soumettre la transaction
        try:
            response = submit_and_wait(escrow_create, client, sender_wallet)
            tx_hash = response.result['hash']
            sequence = response.result['Sequence']
            logger.info(f"Escrow créé. Hash de transaction: {tx_hash}, Séquence: {sequence}")
            return tx_hash, sequence
        except Exception as e:
            logger.error(f"Erreur lors de la création de l'escrow: {str(e)}")
            raise
    else:
        # Simuler un escrow
        tx_hash = f"simulated_escrow_{job_id}_{datetime.utcnow().isoformat()}"
        sequence = int(datetime.utcnow().timestamp())
        logger.info(f"Escrow simulé. Hash de transaction: {tx_hash}, Séquence: {sequence}")
        return tx_hash, sequence

def release_escrow(sender_wallet, destination_address, amount_xrp, job_id):
    """
    Libère un escrow XRPL.
    
    Args:
        sender_wallet: Wallet XRPL du broker
        destination_address: Adresse XRPL du destinataire (worker)
        amount_xrp: Montant en XRP à libérer
        job_id: ID du job associé
        
    Returns:
        Hash de la transaction
    """
    logger.info(f"Libération d'un escrow de {amount_xrp} XRP pour {destination_address}")
    
    # Pour cette démo, nous simulons la libération d'un escrow
    # Dans une implémentation réelle, il faudrait récupérer la séquence de l'escrow
    # et utiliser EscrowFinish pour le libérer
    
    from xrpl_utils.payment import send_xrp_payment
    
    # Simuler un paiement direct
    tx_hash = send_xrp_payment(sender_wallet, destination_address, amount_xrp, f"Payment for job {job_id}")
    
    logger.info(f"Escrow libéré. Hash de transaction: {tx_hash}")
    return tx_hash