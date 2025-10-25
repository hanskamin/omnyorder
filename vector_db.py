import chromadb
from chromadb.utils import embedding_functions
import os
from dotenv import load_dotenv

load_dotenv()


class VectorDB:
    """Simple vector database using ChromaDB and OpenAI embeddings"""
    
    def __init__(self, db_path: str = "./chroma_db", collection_name: str = "documents"):
        """Initialize the vector database"""
        self.client = chromadb.PersistentClient(path=db_path)
        
        # Create OpenAI embedding function
        self.openai_ef = embedding_functions.OpenAIEmbeddingFunction(
            api_key=os.getenv("OPENAI_API_KEY"),
            model_name="text-embedding-3-small"
        )
        
        # Get or create collection
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            embedding_function=self.openai_ef
        )
    
    def add(self, text: str, doc_id: str, metadata: dict = None):
        """Add a text document to the database"""
        params = {
            "documents": [text],
            "ids": [doc_id]
        }
        if metadata:
            params["metadatas"] = [metadata]
        
        self.collection.add(**params)
    
    def query(self, query_text: str, n_results: int = 5):
        """Search for similar documents"""
        results = self.collection.query(
            query_texts=[query_text],
            n_results=n_results
        )
        return results
    
    def count(self):
        """Get total number of documents"""
        return self.collection.count()


# Example usage
if __name__ == "__main__":
    db = VectorDB()
    
    # Add some text
    db.add("The quick brown fox jumps over the lazy dog", "doc1")
    db.add("Python is a great programming language", "doc2")
    db.add("I love coding in Python", "doc3")
    
    print(f"✅ Added {db.count()} documents\n")
    
    # Query
    print("🔍 Searching for 'programming':")
    results = db.query("programming", n_results=2)
    
    for i, doc in enumerate(results['documents'][0]):
        print(f"{i+1}. {doc}")
        print(f"   Distance: {results['distances'][0][i]:.4f}\n")