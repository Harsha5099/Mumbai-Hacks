import sys
print(f"Python Version: {sys.version}")

print("\n--- TEST 1: OpenAI Embeddings ---")
try:
    from langchain_openai import OpenAIEmbeddings
    print("✅ langchain_openai is working.")
except ImportError as e:
    print(f"❌ FAIL: {e}")

print("\n--- TEST 2: ChromaDB (The Database) ---")
try:
    import chromadb
    print("✅ chromadb is working.")
except ImportError as e:
    print(f"❌ FAIL: {e}")
except Exception as e:
    # Captures specific Windows/SQLite errors
    print(f"❌ CRITICAL CHROMA ERROR: {e}")

print("\n--- TEST 3: LangChain Chroma Connector ---")
try:
    from langchain_chroma import Chroma
    print("✅ langchain_chroma is working.")
except ImportError as e:
    print(f"❌ FAIL: {e}")

print("\n--- DIAGNOSTIC COMPLETE ---")