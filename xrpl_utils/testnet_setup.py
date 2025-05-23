#!/usr/bin/env python3
"""
Utilitaires pour configurer des comptes XRPL sur le testnet.
"""
import logging
import requests
import json
import time

from xrpl_utils.wallet import create_wallet, save_wallet_to_file

logger = logging.getLogger("xrpl_testnet")

# URL du faucet XRPL Testnet
FAUCET_URL = "https://faucet.altnet.rippletest.net/accounts"

def create_funded_wallet(name="Test"):
    """
    Crée un wallet XRPL et le finance via le faucet du testnet.
    
    Args:
        name: Nom du wallet (pour le logging)
        
    Returns:
        Le wallet créé et financé
    """
    logger.info(f"Création d'un wallet financé pour {name}")
    
    try:
        # Essayer d'utiliser le faucet XRPL
        response = requests.post(FAUCET_URL)
        
        if response.status_code == 200:
            # Le faucet a fonctionné, utiliser le wallet créé
            wallet_data = response.json()
        #     logger.info(f"Réponse du faucet: {json.dumps(wallet_data, indent=2)}")  DEBUG
            
            # Créer un wallet à partir des données du faucet
            from xrpl_utils.wallet import SimulatedWallet
            
            wallet = SimulatedWallet(seed=wallet_data['seed'])
            wallet.classic_address = wallet_data['account']['address']
            
            logger.info(f"Wallet {name} créé et financé via le faucet: {wallet.classic_address}")
            return wallet
        else:
            logger.warning(f"Échec de l'utilisation du faucet: {response.text}")
    except Exception as e:
        logger.warning(f"Erreur lors de l'utilisation du faucet: {str(e)}")
    
    # Si le faucet échoue, créer un wallet simulé
    wallet = create_wallet()
    logger.info(f"Wallet {name} créé (non financé): {wallet.classic_address}")
    
    return wallet

def fund_account(address, amount_xrp=1000):
    """
    Finance un compte XRPL via le faucet du testnet.
    
    Args:
        address: Adresse XRPL à financer
        amount_xrp: Montant en XRP à demander (ignoré par le faucet)
        
    Returns:
        True si le financement a réussi, False sinon
    """
    logger.info(f"Financement du compte {address}")
    
    try:
        # Utiliser le faucet XRPL
        response = requests.post(FAUCET_URL, json={"destination": address})
        
        if response.status_code == 200:
            logger.info(f"Compte {address} financé avec succès")
            return True
        else:
            logger.error(f"Échec du financement: {response.text}")
            return False
    except Exception as e:
        logger.error(f"Erreur lors du financement: {str(e)}")
        return False

def setup_test_accounts(num_accounts=3, save_to_file=True):
    """
    Configure plusieurs comptes de test sur le testnet.
    
    Args:
        num_accounts: Nombre de comptes à créer
        save_to_file: Si True, sauvegarde les wallets dans des fichiers
        
    Returns:
        Liste des wallets créés
    """
    logger.info(f"Configuration de {num_accounts} comptes de test")
    
    wallets = []
    
    for i in range(num_accounts):
        name = f"Account_{i+1}"
        wallet = create_funded_wallet(name)
        wallets.append(wallet)
        
        if save_to_file:
            save_wallet_to_file(wallet, f"{name.lower()}_wallet.json")
        
        # Attendre un peu entre chaque création pour éviter de surcharger le faucet
        if i < num_accounts - 1:
            time.sleep(1)
    
    return wallets