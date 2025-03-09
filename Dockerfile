FROM python:3.12-alpine

ENV TZ=America/New_York

COPY ./requirements.txt /requirements.txt

RUN apk add --no-cache \
  cronie logrotate aws-cli \
  bash procps \
  curl jq \
  && rm -rf /var/cache/apk/* \
  && pip install --no-cache-dir --upgrade pip \
  && pip install --no-cache-dir --upgrade -r /requirements.txt \
  && rm -f /requirements.txt \
  && mkdir -p /etc/cron.d \
  && mkdir -p /var/log/cupcake

COPY ./cupcake /cupcake
WORKDIR /cupcake

EXPOSE 3124
CMD ["./cupcake-entry.sh"]
