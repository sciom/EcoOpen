import streamlit as st
import chromadb
from langchain_ollama import OllamaLLM, OllamaEmbeddings
from langchain_community.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain_core.prompts import PromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
from langchain.embeddings.base import Embeddings
import os
import tempfile

# Streamlit app configuration
st.set_page_config(page_title="PDF Stylized Facts Generator", page_icon="📄")
st.title("📄 PDF to Stylized Facts Generator")
st.markdown("This application 'reads' a PDF document and generates stylized facts based on its topic.")
st.markdown("Upload a PDF to generate stylized facts based on its topic.")

# Initialize Ollama LLM and Embeddings
llm = OllamaLLM(model="phi4", base_url="http://localhost:11434")  # LLM for generation

class SafeOllamaEmbeddings(Embeddings):
    def __init__(self, base_embeddings):
        self.base_embeddings = base_embeddings

    def embed_documents(self, texts):
        # Ensure only strings are passed
        clean_texts = [str(t) if not isinstance(t, str) else t for t in texts]
        return self.base_embeddings.embed_documents(clean_texts)

    def embed_query(self, text):
        return self.base_embeddings.embed_query(str(text))

embeddings = SafeOllamaEmbeddings(OllamaEmbeddings(model="nomic-embed-text", base_url="http://localhost:11434"))  # Use embedding model

# Test embedding functionality
test_embedding = embeddings.embed_query("This is a test string.")
print("Test embedding length:", len(test_embedding))

# Initialize ChromaDB client
chroma_client = chromadb.PersistentClient(path="./chroma_db")
collection_name = "pdf_documents_v2"

# Function to process PDF and store in ChromaDB
def process_pdf(pdf_file):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
        tmp_file.write(pdf_file.read())
        tmp_file_path = tmp_file.name

    loader = PyPDFLoader(tmp_file_path)
    documents = loader.load()

    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    splits = text_splitter.split_documents(documents)

    # Only keep splits that have non-empty string content
    texts = [str(doc.page_content) for doc in splits if isinstance(doc.page_content, str) and doc.page_content.strip()]
    metadatas = [doc.metadata for doc in splits if isinstance(doc.page_content, str) and doc.page_content.strip()]

    if not texts:
        raise ValueError("No valid text chunks found in the PDF.")

    # Debugging output
    print("Sample texts:", texts[:2])
    print("Sample metadatas:", metadatas[:2])
    print("Types in texts:", [type(t) for t in texts[:2]])

    # Create or get Chroma vector store
    vectorstore = Chroma.from_texts(
        texts=texts,
        embedding=embeddings,
        metadatas=metadatas,
        client=chroma_client,
        collection_name=collection_name
    )

    os.unlink(tmp_file_path)
    return vectorstore

# Function to detect topic
def detect_topic(vectorstore):
    retriever = vectorstore.as_retriever(search_kwargs={"k": 5})
    topic_prompt = PromptTemplate(
        input_variables=["context"],
        template="Based on the following context, identify the main topic of the document in one sentence:\n\n{context}"
    )
    topic_chain = {"context": retriever | (lambda docs: "\n".join([doc.page_content for doc in docs]))} | topic_prompt | llm | StrOutputParser()
    topic = topic_chain.invoke({})
    return topic

# Function to generate stylized facts
def generate_stylized_facts(vectorstore, topic):
    retriever = vectorstore.as_retriever(search_kwargs={"k": 5})
    facts_prompt = PromptTemplate(
        input_variables=["context", "topic"],
        template="Given the topic '{topic}' and the following context, generate 3-10 concise stylized facts in a professional tone:\n\n{context}"
    )
    facts_chain = {
        "context": retriever | (lambda docs: "\n".join([doc.page_content for doc in docs])),
        "topic": lambda _: topic
    } | facts_prompt | llm | StrOutputParser()
    facts = facts_chain.invoke({})
    return facts

# Streamlit UI
uploaded_file = st.file_uploader("Choose a PDF file", type="pdf")

if uploaded_file is not None:
    try:
        # Initialize progress bar and status
        progress_bar = st.progress(0, text="Starting...")
        status_text = st.empty()

        # Step 1: Process PDF
        status_text.text("Processing PDF...")
        vectorstore = process_pdf(uploaded_file)
        progress_bar.progress(33, text="PDF processed")
        status_text.text("PDF processed successfully!")

        # Step 2: Detect topic
        status_text.text("Detecting topic...")
        topic = detect_topic(vectorstore)
        progress_bar.progress(66, text="topic detected")
        status_text.text("topic detected!")

        # Step 3: Generate stylized facts
        status_text.text("Generating stylized facts...")
        facts = generate_stylized_facts(vectorstore, topic)
        progress_bar.progress(100, text="Stylized facts generated")
        status_text.text("Processing complete!")

        # Display results
        st.subheader("Document topic")
        st.write(topic)
        st.subheader("Stylized Facts")
        st.markdown(facts)

    except Exception as e:
        st.error(f"An error occurred: {str(e)}")
        progress_bar.progress(0, text="Error occurred")
        status_text.text("Error occurred")
else:
    st.info("Please upload a PDF file to begin.")

# Footer
st.markdown("---")
st.markdown("AdvanDEB, Powered by LangChain, Phi4, ChromaDB, and Streamlit")