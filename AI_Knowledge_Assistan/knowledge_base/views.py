from rest_framework import views, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from knowledge_base.models import Document
from knowledge_base.rag_pipeline import ingest_document_to_vector_db
import threading  # Използваме threading за демонстрация на асинхронно действие


class DocumentUploadView(views.APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        # 1. Проверка дали има файл в заявката
        if 'file' not in request.FILES:
            return Response({"error": "No file provided."}, status=status.HTTP_400_BAD_REQUEST)

        uploaded_file = request.FILES['file']

        # 2. Създаване на запис в Django модела
        document_instance = Document.objects.create(
            user=request.user,
            title=uploaded_file.name,
            uploaded_file=uploaded_file,
            ingestion_status='PENDING'
        )

        # 3. Асинхронно стартиране на процеса на инжектиране
        # В Production: Заменете това с Celery/Redis за надеждност
        threading.Thread(target=ingest_document_to_vector_db, args=(document_instance,)).start()

        return Response({
            "message": "File uploaded and ingestion started.",
            "document_id": document_instance.id
        }, status=status.HTTP_201_CREATED)
