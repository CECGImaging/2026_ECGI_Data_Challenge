
FROM python:3.10

WORKDIR /code

COPY ./requirements.txt /code/requirements.txt

RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt

COPY app /code/app

# mount the ground-truth scoring data to container
COPY GT_Data_test /data/GT_Data_test

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "80"]
