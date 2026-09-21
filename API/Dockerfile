# Image de developpement de l'API : sert a lancer uvicorn et son Swagger
# sans rien installer sur le poste (voir docker/docker-compose.yml, service
# "api"). Le code est monte en volume, pas copie : une modification est
# prise en compte a chaud grace a --reload.
FROM python:3.12-slim

WORKDIR /api

# Les dependances sont installees a part du code : tant que requirements.txt
# ne change pas, Docker reutilise cette couche et le rebuild est instantane.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 8000

CMD ["uvicorn", "src.app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
