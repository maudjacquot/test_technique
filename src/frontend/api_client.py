import streamlit as st
import requests
import json
from pathlib import Path
from typing import Optional, Dict, Any

class APIClient:
    """Client centralisé pour toutes les requêtes API avec authentification."""
    
    def __init__(self):
        self.config = self._load_config()
        self.api_url = self.config["api_url"]
        self.api_key = self.config["api_key"]
    
    def _load_config(self) -> Dict[str, Any]:
        """Charge la configuration frontend."""
        config_path = Path("files/config-front.json")
        if not config_path.exists():
            st.error("⚠️ Fichier config-front.json manquant!")
            st.info("Créez un fichier config-front.json avec:\n```json\n{\n  \"api_url\": \"http://localhost:8000\",\n  \"api_key\": \"votre_clé\"\n}\n```")
            st.stop()
        
        try:
            with open(config_path, "r") as f:
                return json.load(f)
        except Exception as e:
            st.error(f"❌ Erreur lors du chargement de config-front.json: {e}")
            st.stop()
    
    def _get_headers(self) -> Dict[str, str]:
        """Retourne les headers avec l'API Key."""
        return {
            "X-API-Key": self.api_key,
            "Content-Type": "application/json"
        }
    
    def _handle_response(self, response: requests.Response) -> Optional[Dict]:
        """Gère les erreurs HTTP communes."""
        if response.status_code == 401:
            st.error("🔒 Authentification échouée - Clé API invalide")
            return None
        elif response.status_code == 429:
            st.error("⚠️ Trop de requêtes - Ralentissez")
            return None
        elif response.status_code == 404:
            st.error("❌ Ressource non trouvée")
            return None
        elif response.status_code >= 500:
            st.error(f"❌ Erreur serveur ({response.status_code})")
            st.error(response.text)
            return None
        elif response.status_code != 200:
            st.error(f"❌ Erreur {response.status_code}: {response.text}")
            return None
        
        return response.json()
    
    # === Méthodes pour les endpoints chat ===
    
    def chat_completion(self, user: str, question: str, model: Optional[str] = None) -> Optional[Dict]:
        """Appelle l'endpoint /v1/chat/completions."""
        payload = {
            "user": user,
            "input": question
        }
        if model:
            payload["model"] = model
        
        try:
            response = requests.post(
                f"{self.api_url}/v1/chat/completions",
                headers=self._get_headers(),
                json=payload,
                timeout=60
            )
            return self._handle_response(response)
        
        except requests.exceptions.Timeout:
            st.error("⏱️ Timeout - Le serveur met trop de temps à répondre")
            return None
        except requests.exceptions.ConnectionError:
            st.error("🔌 Impossible de se connecter à l'API")
            return None
        except Exception as e:
            st.error(f"❌ Erreur inattendue: {str(e)}")
            return None
    
    # === Méthodes pour les endpoints admin ===
    
    def list_files(self, recursive: bool = False, ext: Optional[str] = None) -> Optional[Dict]:
        """Liste les fichiers via /admin/raw-files."""
        params = {"recursive": recursive}
        if ext:
            params["ext"] = ext
        
        try:
            response = requests.get(
                f"{self.api_url}/admin/raw-files",
                headers=self._get_headers(),
                params=params,
                timeout=10
            )
            return self._handle_response(response)
        except Exception as e:
            st.error(f"❌ Erreur lors de la récupération des fichiers: {e}")
            return None
    
    def upload_file(self, file) -> Optional[Dict]:
        """Upload un fichier via /admin/raw-files/upload-and-ingest."""
        try:
            # Pour l'upload, on garde Content-Type auto (multipart/form-data)
            headers = {"X-API-Key": self.api_key}
            
            files = {"file": (file.name, file, file.type)}
            response = requests.post(
                f"{self.api_url}/admin/raw-files/upload-and-ingest",
                headers=headers,
                files=files,
                timeout=120  # Upload peut être long
            )
            return self._handle_response(response)
        except Exception as e:
            st.error(f"❌ Erreur lors de l'upload: {e}")
            return None
    
    def delete_file(self, rel_path: str) -> Optional[Dict]:
        """Supprime un fichier via /admin/raw-files/{rel_path}."""
        try:
            from urllib.parse import quote
            encoded_path = quote(rel_path, safe='')
            
            response = requests.delete(
                f"{self.api_url}/admin/raw-files/{encoded_path}",
                headers=self._get_headers(),
                timeout=30
            )
            return self._handle_response(response)
        except Exception as e:
            st.error(f"❌ Erreur lors de la suppression: {e}")
            return None


# Instance globale réutilisable
@st.cache_resource
def get_api_client() -> APIClient:
    """Retourne une instance unique du client API (mise en cache)."""
    return APIClient()