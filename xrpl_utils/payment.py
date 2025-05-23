#!/usr/bin/env python3
"""
Utilitaires pour effectuer des paiements XRPL.
"""
import logging
from datetime import datetime

logger = logging.getLogger("xrpl_payment")

try:
    import xrpl
    from xrpl.models.transactions import Payment
    from xrpl.wallet import Wallet
    from xrpl.clients import JsonRpcClient
    from xrpl.transaction import submit_and_wait
    XRPL_AVAILABLE = True
except ImportError:
    logger.warning("xrpl-py non disponible, utilisation de paiements simulés")
    XRPL_AVAILABLE = False

# URL du serveur XRPL Testnet
TESTNET_URL = "https://s.altnet.rippletest.net:51234"

def send_xrp_payment(sender_wallet, destination_address, amount_xrp, memo=None):
    """
    Envoie un paiement XRP.
    
    Args:
        sender_wallet: Wallet XRPL de l'expéditeur
        destination_address: Adresse XRPL du destinataire
        amount_xrp: Montant en XRP à envoyer
        memo: Mémo optionnel pour la transaction
        
    Returns:
        Hash de la transaction
    """
    logger.info(f"Envoi de {amount_xrp} XRP à {destination_address}")
    
    if XRPL_AVAILABLE and isinstance(sender_wallet, Wallet):
        # Convertir le montant en drops (1 XRP = 1,000,000 drops)
        amount_drops = int(amount_xrp * 1_000_000)
        
        # Créer le client XRPL
        client = JsonRpcClient(TESTNET_URL)
        
        # Créer la transaction de paiement
        payment = Payment(
            account=sender_wallet.classic_address,
            destination=destination_address,
            amount=str(amount_drops)
        )
        
        # Soumettre la transaction
        try:
            response = submit_and_wait(payment, client, sender_wallet)
            tx_hash = response.result['hash']
            logger.info(f"Paiement effectué. Hash de transaction: {tx_hash}")
            return tx_hash
        except Exception as e:
            logger.error(f"Erreur lors de l'envoi du paiement: {str(e)}")
            raise
    else:
        # Simuler un paiement
        tx_hash = f"simulated_payment_{datetime.utcnow().isoformat()}"
        logger.info(f"Paiement simulé. Hash de transaction: {tx_hash}")
        return tx_hash