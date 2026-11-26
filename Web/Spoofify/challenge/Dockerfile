FROM gcr.io/kctf-docker/challenge@sha256:0f7d757bcda470c3bbc063606335b915e03795d72ba1d8fdb6f0f9ff3757364f

RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -yq --no-install-recommends \
        python3 python3-pip python3-venv \
    && rm -rf /var/lib/apt/lists/*

RUN python3 -m venv /home/user/venv
COPY requirements.txt /tmp/requirements.txt
RUN /home/user/venv/bin/pip install --no-cache-dir -r /tmp/requirements.txt

COPY app.py /home/user/app.py
COPY flag /flag
RUN chmod 444 /flag

CMD kctf_setup && \
    kctf_drop_privs \
    /home/user/venv/bin/gunicorn -w 2 --threads 2 --worker-tmp-dir /dev/shm -b 0.0.0.0:1337 --chdir /home/user app:app
