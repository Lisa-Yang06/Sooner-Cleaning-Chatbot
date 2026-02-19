**🧹 Soonercleaning RAG Chatbot**

A retrieval-augmented generation (RAG) chatbot designed to support overseas clients across time zones with 24/7 automated responses.
Built for Soonercleaning Co. Ltd (Beijing, China).

**🚀 Overview**

This project implements a production-oriented customer support chatbot powered by:

OpenAI embeddings (text-embedding-3-small)

FAISS vector search (IndexFlatIP)

Retrieval-Augmented Generation (RAG)

Web-scraped product documentation and structured catalogs

The system enables real-time, context-aware responses to client inquiries, improving cross-border communication efficiency and reducing unmatched queries by ~20%.

**🧠 System Architecture**

Document Ingestion

Scraped official website content

Parsed product catalogs (PDF → text via PyMuPDF)

Cleaned and chunked documents

Embedding Pipeline

Generated semantic embeddings using OpenAI API

Stored embeddings in FAISS IndexFlatIP (cosine similarity)

Retrieval Layer

Query → embedding

Nearest neighbor search

Top-k document retrieval

Generation Layer

Retrieved context passed to LLM

Context-aware response generation

**🏗 Tech Stack**

Python

OpenAI API

FAISS (IndexFlatIP)

PyMuPDF

Web scraping tools

Vector similarity search

**📈 Impact**

Reduced unmatched customer queries by ~20%

Improved semantic retrieval recall

Enabled 24/7 automated support across time zones

Enhanced product information accessibility for overseas clients

**🌍 Motivation**

Customer support across time zones requires scalable, reliable, and semantically robust automation.
This project demonstrates how RAG pipelines can bridge domain-specific knowledge bases with large language models for practical business deployment.
