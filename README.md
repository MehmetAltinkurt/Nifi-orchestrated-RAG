# NiFi Orchestrated RAG (Test Project)

This project is a simple end-to-end RAG (Retrieval-Augmented Generation) system orchestrated by Apache NiFi.
It was developed as part of the **AI Engineer** assessment.

---

## Overview

The system ingests PDF files using NiFi, chunks and embeds the text, stores embeddings in **Qdrant**,  
and serves two RAG variants (A and B) through a **FastAPI** service.

- Variant **A** → context only (no LLM)
- Variant **B** → context + LLM-generated answer  
  The two are compared via **online feedback** and **offline cosine similarity** evaluation.

---

## Components

| Component | Description |
|------------|--------------|
| **NiFi** | Manages data flow: GetFile → InvokeHTTP |
| **FastAPI** | Handles `/ingest-file`, `/query`, `/feedback`, `/offline_eval` etc. |
| **Qdrant** | Vector database for storing document embeddings |
| **Makefile** | Used for setup, running, and generating reports |

---

## How to Run

1. **Start everything**
   ```bash
   make up


2. **NiFi UI**
URL → https://localhost:8443/nifi
Username → admin
Password → adminadmin

3. **Qdtant**
URL → http://localhost:6333/dashboard

4. **API**
Swager → http://localhost:8000/docs

5. **ingest file**
put a pdf file into data/inbox folder

6. **Create report**
    put qa json file into data folder

   ```bash
   make offline-eval

7. **stop everything**
    ```bash
    make down

8. **remove environment**
    ```bash
   make clean

9. **clear vector database**
    ```bash
   make qdrant-reset