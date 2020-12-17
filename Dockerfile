FROM python:3.8-alpine
WORKDIR /app
COPY requirements.txt /app/
RUN apk update && apk add postgresql-dev gcc python3-dev musl-dev
RUN pip install -r requirements.txt
COPY src/ /app/src
COPY wsgi.py /app/
RUN apk add curl
#CMD ["tail", "-f", "/dev/null"]
CMD ["gunicorn", "-b", "0.0.0.0:5000", "wsgi:app"]
