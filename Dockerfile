FROM python:3.10
# Disabling Bytecode (.pyc) Files
ENV PYTHONDONTWRITEBYTECODE=1
# python output streams are sent straight to container log without being first buffered
ENV PYTHONUNBUFFERED=1
# create working directory
WORKDIR /teleword
# copy all local files to container workdir
COPY . .
# requirements
RUN pip install --upgrade pip
RUN pip install -r requirements.txt
# start teleword
CMD ["python", "-u", "teleword.py"]
