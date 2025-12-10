# **README**

# Test Technique - RAG Chatbot PoC

## Contexte
Ce projet est une preuve de concept pour un **chatbot interne sécurisé** destiné à un cabinet d’avocats.  
L’objectif est de permettre à l’équipe de rechercher rapidement des informations dans des documents juridiques, via un **RAG (Retrieval-Augmented Generation)**.

Le projet combine :
- **FastAPI** pour l’API backend (gestion des documents et orchestration du LLM)  
- **Streamlit** pour l’interface utilisateur  
- **Chroma + LlamaIndex** pour la vectorisation et la recherche de documents  
- **OpenAI API** (ou modèle compatible) pour les réponses du chatbot

---

## Structure du projet

.
├── .env
├── .gitignore
├── App.py                  # Entrée Streamlit
├── main.py                 # Entrée FastAPI
├── data/                   # Documents source et index Chroma
├── files/                  # Config et prompts
├── pages/                  # Pages Streamlit (nécessaire pour st.switch_page)
├── requirements.txt
├── README.md
└── src/
    ├── backend/
    │   ├── api/            # Endpoints FastAPI (admin)
    │   └── services/       # Logic métier : LLM, ingestion, orchestrator, retriever
    └── frontend/           # Interface Streamlit si besoin d’organisation interne

---

## Installation

1. Cloner le repo

```bash
git clone https://github.com/AI-Sisters/test_technique.git
cd test_technique
```

2. Créer un environnement Python

```bash
python -m venv .venv
source .venv/bin/activate        # macOS/Linux
.venv\Scripts\activate           # Windows
```

3. Installer les dépendances

```bash
pip install -r requirements.txt
```

4. Configurer l’API key
- Créer `.env` et ajouter votre clé OpenAI :

```ini
API_KEY=...
```

---

## Lancer l’application

### FastAPI (API backend)

```bash
uvicorn main:app --reload
```

- Health check : `http://127.0.0.1:8000/health`  
- Endpoint chat (OpenAI-compatible) : `POST http://127.0.0.1:8000/v1/chat/completions`  
- Admin endpoints disponibles sous `/admin`

### Streamlit (interface utilisateur)

```bash
streamlit run App.py
```

- Menu à gauche pour naviguer entre **Assistant RAG** et **Admin**  
- Les pages sont dans `pages/` à la racine pour `st.switch_page()`  

---

## Utilisation

### Streamlit

1. **Assistant RAG**  
   - Poser une question et obtenir une réponse basée uniquement sur les documents vectorisés.  
   - Historique des conversations (bonus).

2. **Admin**  
   - Upload, suppression et ingestion des documents.  
   - Reset de la base vectorielle Chroma si besoin.

### API

- Upload + ingestion d’un fichier : `/admin/raw-files/upload-and-ingest`  
- Liste des fichiers : `/admin/raw-files`  
- Suppression d’un fichier : `/admin/raw-files/{rel_path}`  
- Reset vecteurs : `/admin/vector/reset`  

---

## Configuration

- `files/config.json` contient les paramètres principaux :
  - `data_path` : dossier contenant les documents
  - `chroma_path` : dossier pour la base vectorielle
  - `collection_name` : nom de la collection Chroma
  - `chunk_size`, `chunk_overlap` : paramètres de découpe des documents
  - `top_k` : nombre de chunks retournés par la recherche
  - `prompt_system` : fichier de system prompt

---

## Notes

- Tous les documents sont **anonymisés** pour le PoC.  
- LLM utilisé via API : OpenAI ou compatible.    
- Pour tests et maintenance, la logique métier est centralisée dans `src/backend/services`.  

---

## TODO

- Ajouter logs 
- History à faire 
- API sécurisé
- README à finir 
