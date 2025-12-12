# **README**

# Test Technique - RAG Chatbot PoC

## Contexte
Ce projet est une preuve de concept pour un **chatbot interne sécurisé** destiné à un cabinet d'avocats.  
L'objectif est de permettre à l'équipe de rechercher rapidement des informations dans des documents juridiques, via un **RAG (Retrieval-Augmented Generation)**.

Le projet combine :
- **FastAPI** pour l'API backend (gestion des documents et orchestration du LLM)  
- **Streamlit** pour l'interface utilisateur  
- **Chroma + LlamaIndex** pour la vectorisation et la recherche de documents  
- **OpenAI API** (ou modèle compatible) pour les réponses du chatbot

---

## Structure du projet

````
.
├── .env                                    # Variables d'environnement backend (gitignored)
├── .gitignore
├── App.py                                  # Entrée Streamlit
├── main.py                                 # Entrée FastAPI
├── data/                                   # Documents source et base vectorielle
│   ├── chroma/                             # Base vectorielle Chroma
│   │   └── chroma.sqlite3
│   ├── consultation_fiscalite_2024.txt    # Exemples de documents
│   ├── contrat_commercial_partenaireA.txt
│   ├── historique_contentieux.csv
│   ├── jurisprudence_cassation2023.html
│   ├── mise_en_demeure_impaye_clientZ.txt
│   └── note_droit_societes_2025.html
├── files/                                  # Configuration et prompts
│   ├── config-front.json                   # Config frontend avec API Key (gitignored)
│   ├── config.json                         # Config backend
│   └── prompts/
│       └── default_system_prompt.txt
├── logs/                                   # Logs applicatifs (gitignored)
│   └── app.log
├── pages/                                  # Pages Streamlit
│   ├── 1_🧠_Assistant_RAG.py
│   └── 2_⚙️_Admin.py
├── requirements.txt
├── README.md
└── src/
    ├── backend/
    │   ├── api/                            # Endpoints FastAPI
    │   │   ├── admin.py                    # Routes admin (upload, delete, list)
    │   │   └── security.py                 # Vérification API Key
    │   └── services/                       # Logic métier
    │       ├── llm_client.py               # Client OpenAI
    │       ├── load_files.py               # Ingestion documents
    │       ├── logger.py                   # Configuration logging
    │       ├── orchestrator.py             # Orchestration RAG
    │       └── retriever.py                # Recherche vectorielle
    └── frontend/
        └── api_client.py                   # Client API centralisé avec authentification
````

---

## Installation

### 1. Cloner le repo

```bash
git clone https://github.com/AI-Sisters/test_technique.git
cd test_technique
```

### 2. Créer un environnement Python

```bash
python -m venv .venv
source .venv/bin/activate        # macOS/Linux
.venv\Scripts\activate           # Windows
```

### 3. Installer les dépendances

```bash
pip install -r requirements.txt
```

### 4. Configuration de la sécurité

#### **a) Backend : Fichier `.env`**

Créer un fichier `.env` à la racine du projet avec :

```ini
# Clé OpenAI pour le LLM
API_KEY="sk-proj-votre_cle_openai"

# Clé d'authentification pour le frontend Streamlit
FRONTEND_API_KEY="votre_cle_secrete_super_longue_123456"
```

#### **b) Frontend : Fichier `files/config-front.json`**

Créer un fichier `files/config-front.json` avec :

```json
{
  "api_url": "http://localhost:8000",
  "api_key": "votre_cle_secrete_super_longue_123456"
}
```

⚠️ **Important** : La valeur de `api_key` doit être **identique** à `FRONTEND_API_KEY` dans `.env`.

> 🔒 **Ces fichiers sont dans `.gitignore` et ne doivent JAMAIS être commités.**

---

## Lancer l'application

### 1. FastAPI (API backend)

```bash
uvicorn main:app --reload
# ou 
python -m uvicorn main:app --reload
```

L'API sera accessible sur `http://127.0.0.1:8000`

- Health check : `http://127.0.0.1:8000/health`  
- Documentation interactive : `http://127.0.0.1:8000/docs`
- Endpoint chat (OpenAI-compatible) : `POST http://127.0.0.1:8000/v1/chat/completions`  
- Admin endpoints : `/admin/*`

### 2. Streamlit (interface utilisateur)

Dans un **nouveau terminal** :

```bash 
streamlit run App.py
```

L'interface sera accessible sur `http://localhost:8501`

- Menu à gauche pour naviguer entre **Assistant RAG** et **Admin**  

---

## Utilisation

### Interface Streamlit

#### **1. 🧠 Assistant RAG**
- Poser des questions au chatbot
- Recevoir des réponses basées exclusivement sur les documents vectorisés
- Voir les statistiques de tokens utilisés

**Exemples de questions** :
- "Quels sont les délais de prescription dans le contentieux fiscal ?"
- "Résume le contrat avec le partenaire A"
- "Quelles sont les jurisprudences importantes de 2023 ?"

#### **2. ⚙️ Admin**
- **Upload de documents** : Ajouter des fichiers `.txt`, `.html`, `.csv`
- **Liste des documents** : Voir tous les fichiers indexés avec leur taille
- **Suppression** : Retirer un document de la base vectorielle (supprime aussi les embeddings)

---

## Sécurité

### 🔐 Authentification par API Key

Tous les endpoints (sauf `/health` et `/docs`) sont protégés par une API Key envoyée via le header `X-API-Key`.

**Architecture de sécurité** :
1. Le frontend Streamlit lit `files/config-front.json` au démarrage
2. Chaque requête vers l'API inclut le header `X-API-Key`
3. FastAPI vérifie la clé via le middleware `verify_api_key()`
4. Si invalide → erreur 401 Unauthorized

### 🛡️ Protection implémentée

- ✅ **Authentification** : API Key requise pour tous les endpoints sensibles
- ✅ **Validation des inputs** : Vérification des formats (`.txt`, `.html`, `.csv`) et tailles de fichiers
- ✅ **Path traversal protection** : Empêche l'accès aux fichiers hors du dossier `data/`
- ✅ **Gestion d'erreurs sécurisée** : Pas de fuite d'informations techniques
- ✅ **Logging** : Traçabilité des actions dans `logs/app.log`

---

## Configuration

### `files/config-front.json` (Frontend)

```json
{
  "api_url": "http://localhost:8000",
  "api_key": "votre_cle_secrete_super_longue_123456"
}
```

**Paramètres** :
- `api_url` : URL de l'API FastAPI
- `api_key` : Clé d'authentification (doit correspondre à `FRONTEND_API_KEY` dans `.env`)

---

## Dépannage

### ❌ Erreur "Missing FRONTEND_API_KEY in .env"

**Cause** : Le fichier `.env` n'existe pas ou ne contient pas `FRONTEND_API_KEY`

**Solution** :
1. Vérifiez que `.env` est à la racine du projet
2. Vérifiez qu'il contient bien `FRONTEND_API_KEY=...`
3. Vérifiez que `load_dotenv()` est appelé **en premier** dans `main.py`
4. Redémarrez FastAPI après modification

### ❌ Erreur 401 dans Streamlit

**Cause** : La clé API dans `files/config-front.json` ne correspond pas à celle dans `.env`

**Solution** :
1. Vérifiez que `files/config-front.json` existe
2. Vérifiez que `api_key` dans `config-front.json` est **identique** à `FRONTEND_API_KEY` dans `.env`
3. Redémarrez Streamlit

**Solution** :
1. Vérifiez que le fichier existe
2. Vérifiez que `load_dotenv()` est appelé **avant** les imports dans `main.py`
3. Vérifiez que tous les dossiers ont un `__init__.py` (peut être vide)

### ❌ Streamlit : "config-front.json manquant"

**Cause** : Le fichier n'existe pas ou le chemin est incorrect

**Solution** :
1. Créer `files/config-front.json` (dans le dossier `files/`, pas à la racine)
2. Vérifier dans `src/frontend/api_client.py` que le chemin est correct :

```python
config_path = Path("files/config-front.json")
```

### ❌ Chroma ne trouve pas les documents

**Causes possibles** :
- Les fichiers ne sont pas dans `data/`
- L'ingestion a échoué
- La collection Chroma est vide

**Solutions** :
1. Vérifiez que les fichiers sont bien dans `data/` (pas dans un sous-dossier)
2. Uploadez un fichier via l'interface Admin
3. Vérifiez les logs dans `logs/app.log`
4. En dernier recours : Reset de la base via `/admin/vector/reset`
---

## Notes techniques

### Architecture

Le projet suit une architecture en couches :

1. **Frontend (Streamlit)** → Interface utilisateur
   - `App.py` : Page d'accueil
   - `pages/` : Pages de navigation
   - `src/frontend/api_client.py` : Client API centralisé

2. **API Layer (FastAPI)** → Endpoints REST
   - `main.py` : Point d'entrée
   - `src/backend/api/` : Routes et sécurité

3. **Service Layer** → Logique métier
   - `orchestrator.py` : Orchestration RAG
   - `retriever.py` : Recherche vectorielle
   - `llm_client.py` : Appels OpenAI
   - `load_files.py` : Ingestion documents

4. **Data Layer** → Stockage
   - `data/` : Documents source
   - `data/chroma/` : Base vectorielle Chroma

### Technologies utilisées

- **Backend** : FastAPI 0.100+, Python 3.12+
- **Frontend** : Streamlit 1.30+
- **RAG** : LlamaIndex, Chroma DB
- **LLM** : OpenAI API (gpt-4.1-mini)
- **Embeddings** : OpenAI text-embedding-3-small
- **Logging** : Loguru

### Données de test

Le projet inclut des **documents anonymisés** pour la démonstration :
- `consultation_fiscalite_2024.txt`
- `contrat_commercial_partenaireA.txt`
- `historique_contentieux.csv`
- `jurisprudence_cassation2023.html`
- `mise_en_demeure_impaye_clientZ.txt`
- `note_droit_societes_2025.html`

Ces fichiers sont des exemples fictifs pour le PoC.

---

## Performance

### Optimisations implémentées

- **Chunking intelligent** : SentenceSplitter avec overlap pour préserver le contexte
- **Top-K retrieval** : Récupère uniquement les 5 chunks les plus pertinents
- **Mise en cache** : Client API mis en cache avec `@st.cache_resource`
- **Streaming upload** : Upload de fichiers par chunks de 1MB

### Limitations actuelles

- **Scalabilité** : Chroma DB en local (pas adapté pour >10 000 documents)
- **Concurrence** : Pas de rate limiting côté serveur
- **Mémoire** : Tous les embeddings chargés en RAM

---

## Auteur

Maud Jacquot
Projet réalisé dans le cadre du test technique pour AI Sisters.

---

## Licence

Ce projet est un PoC à usage interne uniquement.