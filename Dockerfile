FROM tiangolo/uwsgi-nginx-flask:flask

COPY ./app /app

#COPY settings.cfg /app/settings.cfg
#ENV FTZM_CFG="/app/settings.cfg"

COPY requirements.txt /app/requirements.txt
RUN pip install -r /app/requirements.txt
