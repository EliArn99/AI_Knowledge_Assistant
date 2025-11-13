import os
from langchain_community.document_loaders import PyPDFLoader, TextLoader, UnstructuredWordDocumentLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma
from langchain_openai import OpenAIEmbeddings
from knowledge_base.models import Document
from django.conf import settings

# Зареждане на API ключа от env променливи
# (В реален Django проект, това се прави по-сигурно в settings)
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

if not OPENAI_API_KEY:
    # Заредете .env файл за локално тестване
    from dotenv import load_dotenv

    load_dotenv()
    OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
    if not OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY не е намерен.")


def load_and_split_document(file_path):
    """
    Зарежда файла въз основа на неговия тип и го разделя на части (chunks).
    """
    _, file_extension = os.path.splitext(file_path)
    file_extension = file_extension.lower()

    if file_extension == '.pdf':
        loader = PyPDFLoader(file_path)
    elif file_extension == '.txt':
        loader = TextLoader(file_path)
    elif file_extension == '.docx':
        # Unstructured е необходим за DOCX
        loader = UnstructuredWordDocumentLoader(file_path)
    else:
        raise ValueError(f"Тип файл {file_extension} не се поддържа.")

    # Зареждане на документи
    documents = loader.load()

    # Разделяне на текст (chunking)
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1500,  # Размер на частите
        chunk_overlap=150,  # Припокриване между частите
        separators=["\n\n", "\n", ".", "!", "?", ",", " ", ""]
    )

    # Всяка част (chunk) става отделен "document" за Vector DB
    return text_splitter.split_documents(documents)


def ingest_document_to_vector_db(document_instance: Document):
    """
    Основна функция за инжектиране, която се извиква от Django.
    """
    try:
        # Пълният път до файла, качен от Django
        full_file_path = os.path.join(settings.MEDIA_ROOT, document_instance.uploaded_file.name)

        # 1. Зареждане и разделяне
        chunks = load_and_split_document(full_file_path)

        # Добавяме метаданни към всяка част за цитиране
        for chunk in chunks:
            chunk.metadata['source_file'] = document_instance.title
            chunk.metadata['document_id'] = document_instance.id
            chunk.metadata['user_id'] = document_instance.user.id

        # 2. Инициализиране на Embedding модела
        embeddings = OpenAIEmbeddings(openai_api_key=OPENAI_API_KEY)

        # 3. Инициализиране на Vector Store (ChromaDB)
        # Използваме директория 'chroma_db' във файловата система на проекта
        chroma_path = os.path.join(settings.BASE_DIR, "chroma_db")

        # 4. Добавяне на частите във Vector Store
        # Ще използваме ID на потребителя за създаване на отделна 'колекция'
        # (или филтриране) за целите на сигурността на личните данни.
        collection_name = f"user_{document_instance.user.id}_knowledge"

        vector_store = Chroma.from_documents(
            documents=chunks,
            embedding=embeddings,
            persist_directory=chroma_path,
            collection_name=collection_name
        )

        # Запазване на промените във Vector Store (само за ChromaDB)
        vector_store.persist()

        # Обновяване на статуса в Django модела
        document_instance.ingestion_status = 'SUCCESS'
        document_instance.save()

        print(f"Успешно инжектиран документ: {document_instance.title} в колекция {collection_name}")

    except Exception as e:
        print(f"Грешка при инжектиране на {document_instance.title}: {e}")
        document_instance.ingestion_status = 'FAILED'
        document_instance.save()