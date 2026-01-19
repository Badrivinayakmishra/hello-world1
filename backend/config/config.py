"""
KnowledgeVault Configuration Module
Centralized configuration for all backend components
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class Config:
    """Main configuration class for KnowledgeVault"""

    # Base Paths
    BASE_DIR = Path(__file__).parent.parent
    DATA_DIR = BASE_DIR / "data"
    OUTPUT_DIR = BASE_DIR / "output"
    MODELS_DIR = BASE_DIR / "models"

    # Enron Dataset
    ENRON_MAILDIR = os.getenv("ENRON_MAILDIR", "/Users/rishitjain/Downloads/maildir")

    # API Keys
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    LLAMAPARSE_API_KEY = os.getenv("LLAMAPARSE_API_KEY", "llx-UqKQjwEM0stshriDR5HRuYCURE5gkyeymC0E0tL7NFZX5IHG")

    # Model Configuration
    EMBEDDING_MODEL = "sentence-transformers/all-mpnet-base-v2"
    LLM_MODEL = "gpt-4o-mini"
    CLASSIFICATION_MODEL = "distilbert-base-uncased"

    # LlamaParse Configuration
    LLAMAPARSE_RESULT_TYPE = "markdown"
    LLAMAPARSE_VERBOSE = True
    LLAMAPARSE_GPT4O_MODE = True  # Use GPT-4o for image/chart understanding
    LLAMAPARSE_NUM_WORKERS = 4   # Parallel processing for faster parsing

    # Clustering Configuration
    MIN_CLUSTER_SIZE = 5
    MIN_SAMPLES = 3
    UMAP_N_NEIGHBORS = 15
    UMAP_N_COMPONENTS = 5
    UMAP_METRIC = "cosine"

    # Classification Thresholds
    WORK_CONFIDENCE_THRESHOLD = 0.85
    PERSONAL_CONFIDENCE_THRESHOLD = 0.85
    UNCERTAIN_LOWER_BOUND = 0.40

    # Vector Database
    CHROMA_PERSIST_DIR = str(DATA_DIR / "chroma_db")
    COLLECTION_NAME = "knowledgevault"

    # Knowledge Graph
    NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
    NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")

    # RAG Configuration
    TOP_K_RETRIEVAL = 10
    RERANK_TOP_K = 5
    MAX_CONTEXT_LENGTH = 8000

    # Content Generation
    PPT_TEMPLATE_DIR = BASE_DIR / "templates" / "powerpoint"
    VIDEO_OUTPUT_DIR = OUTPUT_DIR / "videos"

    # Gap Analysis
    GAP_ANALYSIS_THRESHOLD = 0.7
    MAX_QUESTIONS_PER_PROJECT = 10

    @classmethod
    def create_directories(cls):
        """Create necessary directories if they don't exist"""
        directories = [
            cls.DATA_DIR,
            cls.OUTPUT_DIR,
            cls.MODELS_DIR,
            cls.DATA_DIR / "processed",
            cls.DATA_DIR / "unclustered",
            cls.DATA_DIR / "employee_clusters",
            cls.DATA_DIR / "project_clusters",
            cls.OUTPUT_DIR / "reports",
            cls.OUTPUT_DIR / "powerpoints",
            cls.OUTPUT_DIR / "videos",
            cls.PPT_TEMPLATE_DIR,
        ]

        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)

        print(f"✓ Created directory structure at {cls.BASE_DIR}")

    @classmethod
    def validate_config(cls):
        """Validate that all required configurations are set"""
        errors = []

        if not cls.OPENAI_API_KEY:
            errors.append("OPENAI_API_KEY not set")

        if not Path(cls.ENRON_MAILDIR).exists():
            errors.append(f"ENRON_MAILDIR not found: {cls.ENRON_MAILDIR}")

        if errors:
            raise ValueError(f"Configuration errors: {', '.join(errors)}")

        print("✓ Configuration validated successfully")
        return True


# Create directories on import
Config.create_directories()
