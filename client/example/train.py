#!/usr/bin/env python3
"""
Exemple de script d'entraînement PyTorch simple.
"""
import os
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset
import numpy as np
import time
import logging
import sys
import traceback

# Définir le chemin du fichier de log dans le répertoire OUTPUT_DIR s'il existe
output_dir = os.environ.get('OUTPUT_DIR', '.')
if output_dir != '.' and not os.path.exists(output_dir):
    os.makedirs(output_dir, exist_ok=True)
log_file = os.path.join(output_dir, 'train.log')

# Configuration du logging pour capturer les erreurs
logging.basicConfig(
    filename=log_file,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filemode='w'  # 'w' pour écraser le fichier à chaque exécution
)
logger = logging.getLogger("train")

# Rediriger stderr vers le logger également
stderr_logger = logging.StreamHandler()
stderr_logger.setLevel(logging.ERROR)
logging.getLogger().addHandler(stderr_logger)

# Configuration pour un fichier log supplémentaire à la racine du workspace
# 'log_file' est le chemin du fichier log principal, défini plus haut et utilisé par basicConfig
# 'logger' est l'instance de logging.getLogger("train")
script_dir = os.path.dirname(os.path.abspath(__file__))
workspace_root = os.path.abspath(os.path.join(script_dir, "..", ".."))
root_train_log_path = os.path.join(workspace_root, "train.log")

abs_primary_log_file = os.path.abspath(log_file)
abs_root_train_log_path = os.path.abspath(root_train_log_path)

if abs_primary_log_file != abs_root_train_log_path:
    # S'assurer que le formatteur et le niveau sont cohérents avec basicConfig
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    fh_root = logging.FileHandler(root_train_log_path, mode='w') # 'w' pour écraser à chaque exécution
    fh_root.setFormatter(formatter)
    fh_root.setLevel(logging.INFO) # Correspond au niveau défini dans basicConfig
    logger.addHandler(fh_root)
    logger.info(f"La journalisation est également active dans : {abs_root_train_log_path}")

# Logique de sélection du device améliorée
if hasattr(torch.backends, "mps") and torch.backends.mps.is_available() and torch.backends.mps.is_built():
    device = torch.device("mps")
elif torch.cuda.is_available():
    device = torch.device("cuda")
else:
    device = torch.device("cpu")

logger.info(f"Utilisation de: {device}")
logger.info(f"OUTPUT_DIR est défini à: {output_dir}")
logger.info(f"Fichier log: {log_file}")

def generate_data(n_samples=100, n_features=20):
    X = np.random.randn(n_samples, n_features).astype(np.float32)
    w = np.random.randn(n_features).astype(np.float32)
    y = (np.dot(X, w) > 0).astype(np.float32)
    return X, y

# Définir un modèle simple
class SimpleModel(nn.Module):
    def __init__(self, input_dim):
        super(SimpleModel, self).__init__()
        self.layer1 = nn.Linear(input_dim, 64)
        self.layer2 = nn.Linear(64, 32)
        self.layer3 = nn.Linear(32, 1)
        
    def forward(self, x):
        x = torch.relu(self.layer1(x))
        x = torch.relu(self.layer2(x))
        x = torch.sigmoid(self.layer3(x))
        return x

def main():
    try:
        logger.info("Starting training...")
        start_time = time.time()
        
        X, y = generate_data(n_samples=100, n_features=20)
        X_tensor = torch.tensor(X)
        y_tensor = torch.tensor(y).reshape(-1, 1)
        
        dataset = TensorDataset(X_tensor, y_tensor)
        dataloader = DataLoader(dataset, batch_size=32, shuffle=True)
        

        model = SimpleModel(input_dim=20).to(device)

        criterion = nn.BCELoss()
        optimizer = optim.Adam(model.parameters(), lr=0.001)
        
        n_epochs = 1
        for epoch in range(n_epochs):
            model.train()
            total_loss = 0
            logger.info(f"--- Epoch {epoch+1}/{n_epochs} ---")
            for i, (batch_X, batch_y) in enumerate(dataloader):
                batch_X, batch_y = batch_X.to(device), batch_y.to(device)
                
                outputs = model(batch_X)
                loss = criterion(outputs, batch_y)
                
                optimizer.zero_grad()
                loss.backward()
                optimizer.step()
                
                total_loss += loss.item()
                if (i + 1) % 5 == 0:
                    logger.info(f"  Epoch {epoch+1}/{n_epochs}, Iteration {i+1}/{len(dataloader)}, Batch Loss: {loss.item():.4f}")
            
            avg_loss = total_loss / len(dataloader)
            logger.info(f"Epoch {epoch+1}/{n_epochs} - Fin, Avg Loss: {avg_loss:.4f}")
        

        # Sauvegarder le modèle directement dans le répertoire OUTPUT_DIR
        model_path = os.path.join(output_dir, "model.pt")
        torch.save(model.state_dict(), model_path)
        
        training_time = time.time() - start_time
        logger.info(f"Entraînement terminé en {training_time:.2f} secondes")
        logger.info(f"Modèle sauvegardé: {model_path}")
        
        model.eval()
        with torch.no_grad():
            test_X = torch.tensor(X[:10]).to(device)
            predictions = model(test_X)
            logger.info("Prédictions sur 10 exemples:")
            logger.info(f"{predictions.cpu().numpy()}")
            
    except Exception as e:
        logger.error(f"Exception lors de l'entraînement: {str(e)}")
        logger.error(traceback.format_exc())
        raise  # Relever l'exception pour que le script renvoie un code d'erreur

if __name__ == "__main__":
    main()