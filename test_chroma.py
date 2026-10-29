from src.vector_store.chroma_db import collection

print("ChromaDB connected successfully!")
print("Collection:", collection.name)
print("Existing indexed tickets:", collection.count())
