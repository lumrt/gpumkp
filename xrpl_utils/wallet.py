#!/usr/bin/env python3
"""
Utilitaires pour gérer les wallets XRPL.
"""
import os
import json
import logging
import hashlib
import base64
from pathlib import Path

logger = logging.getLogger("xrpl_wallet")

try:
    import xrpl
    from xrpl.wallet import Wallet
    XRPL_AVAILABLE = True
except ImportError:
    logger.warning("xrpl-py non disponible, utilisation de wallets simulés")
    XRPL_AVAILABLE = False

class SimulatedWallet:
    """Wallet XRPL simulé pour la démo"""
    
    def __init__(self, seed=None, sequence=None):
        """Initialise un wallet simulé"""
        if seed:
            self.seed = seed
        else:
            # Générer un seed aléatoire
            import random
            self.seed = ''.join(random.choice('0123456789ABCDEF') for _ in range(32))
        
        # Générer une adresse à partir du seed
        self.classic_address = 'r' + hashlib.sha256(self.seed.encode()).hexdigest()[:30]
        self.sequence = sequence or 0
    
    def to_dict(self):
        """Convertit le wallet en dictionnaire"""
        return {
            'seed': self.seed,
            'classic_address': self.classic_address,
            'sequence': self.sequence
        }
    
    @classmethod
    def from_dict(cls, data):
        """Crée un wallet à partir d'un dictionnaire"""
        return cls(seed=data['seed'], sequence=data.get('sequence', 0))

def create_wallet():
    """Crée un nouveau wallet XRPL"""
    logger.info("Création d'un nouveau wallet XRPL")
    
    if XRPL_AVAILABLE:
        # Créer un wallet avec xrpl-py
        wallet = Wallet.create()
        logger.info(f"Wallet créé: {wallet.classic_address}")
        return wallet
    else:
        # Créer un wallet simulé
        wallet = SimulatedWallet()
        logger.info(f"Wallet simulé créé: {wallet.classic_address}")
        return wallet

def save_wallet_to_file(wallet, file_path):
    """Sauvegarde un wallet dans un fichier"""
    logger.info(f"Sauvegarde du wallet dans {file_path}")
    
    # Créer le répertoire parent s'il n'existe pas
    os.makedirs(os.path.dirname(os.path.abspath(file_path)), exist_ok=True)
    
    # Sauvegarder le wallet
    if XRPL_AVAILABLE and isinstance(wallet, Wallet):
        with open(file_path, 'w') as f:
            json.dump({
                'seed': wallet.seed,
                'public_key': wallet.public_key,
                'private_key': wallet.private_key,
                'classic_address': wallet.classic_address
            }, f, indent=2)
    else:
        with open(file_path, 'w') as f:
            json.dump(wallet.to_dict(), f, indent=2)

def load_wallet_from_file(file_path):
    """Charge un wallet depuis un fichier"""
    logger.info(f"Chargement du wallet depuis {file_path}")
    
    with open(file_path, 'r') as f:
        data = json.load(f)
    
    if XRPL_AVAILABLE and 'public_key' in data and 'private_key' in data:
        # Créer un wallet avec xrpl-py
        wallet = Wallet(seed=data['seed'], public_key=data['public_key'], private_key=data['private_key'])
        logger.info(f"Wallet chargé: {wallet.classic_address}")
        return wallet
    else:
        # Créer un wallet simulé
        # Cela gère le cas où XRPL_AVAILABLE est False,
        # ou lorsque XRPL_AVAILABLE est True mais que le fichier wallet
        # ne contient pas public_key/private_key (ex: un SimulatedWallet sauvegardé).
        wallet = SimulatedWallet.from_dict(data)
        logger.info(f"Wallet simulé chargé: {wallet.classic_address}")
        return wallet

def simulate_signature(message, private_key):
    """Simule une signature cryptographique"""
    # Dans une implémentation réelle, cela utiliserait la clé privée pour signer
    # Pour cette démo, nous simulons la signature
    signature_base = hashlib.sha256((message + private_key).encode()).digest()
    return base64.b64encode(signature_base).decode('utf-8')

def verify_signature(message, signature, public_key):
    """Vérifie une signature cryptographique"""
    # Dans une implémentation réelle, cela vérifierait la signature avec la clé publique
    # Pour cette démo, nous simulons la vérification
    expected_signature = simulate_signature(message, public_key)
    return signature == expected_signature