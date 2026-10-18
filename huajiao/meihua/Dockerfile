FROM python:3.12-slim
WORKDIR /srv
COPY meihua/engine /srv/engine
COPY meihua/knowledge_base /srv/knowledge_base
COPY meihua/data /srv/data
ENV PYTHONPATH=/srv
ENV MEIHUA_CSV=/srv/data/2026_us_daily.csv
EXPOSE 8090
CMD ["python3", "-m", "engine.server"]
