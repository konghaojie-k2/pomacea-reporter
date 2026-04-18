FROM python:3.11-slim
WORKDIR /app
COPY index.py .
COPY frontend.html .
ENV PORT=9000
EXPOSE 9000
CMD ["python3", "-u", "index.py"]
