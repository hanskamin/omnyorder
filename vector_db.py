import chromadb
from chromadb.utils import embedding_functions
import os
from dotenv import load_dotenv

load_dotenv()


class VectorDB:
    """Simple vector database using ChromaDB and OpenAI embeddings"""
    
    def __init__(self, collection_name: str = "documents"):
        """Initialize the vector database"""
        self.client = chromadb.HttpClient(host="localhost", port=8000)
        
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
    
    def clear(self):
        """Delete all documents from the collection"""
        ids = self.collection.get()["ids"]
        if ids:
            self.collection.delete(ids=ids)


# Example usage
if __name__ == "__main__":
    db = VectorDB()
    
    # Add dietary preferences
    db.add("User likes Mexican food and Mexican cuisine", "pref_cuisine_mexican")
    db.add("User is vegetarian and does not eat meat, chicken, beef, pork, or fish", "pref_diet_vegetarian")
    db.add("User cannot eat gluten and needs gluten-free options. No wheat, barley, or rye.", "pref_allergy_gluten")
    
    print(f"✅ Added {db.count()} dietary preferences to the database")
    
    # Test query
    print("\n🔍 Testing query for 'dietary preferences':")
    results = db.query("dietary preferences", n_results=3)
    
    for i, doc in enumerate(results['documents'][0]):
        print(f"{i+1}. {doc}")
        print(f"   Distance: {results['distances'][0][i]:.4f}\n")
    