FROM --platform=linux/amd64 gcr.io/kctf-docker/healthcheck@sha256:8aedadc9e6354b67bfec45938eea03e7a55ecc5917c82cbae56f2abf557059d2
COPY healthcheck_loop.sh healthcheck.py healthz_webserver.py solve.py no-open-door /home/user/
CMD kctf_drop_privs bash /home/user/healthcheck_loop.sh & python3 /home/user/healthz_webserver.py
