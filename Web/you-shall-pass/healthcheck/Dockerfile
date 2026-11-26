FROM gcr.io/kctf-docker/healthcheck@sha256:8aedadc9e6354b67bfec45938eea03e7a55ecc5917c82cbae56f2abf557059d2

COPY --chmod=0755 healthcheck_loop.sh healthcheck.py healthz_webserver.py /home/user/
COPY --chmod=0444 flag.txt /home/user/flag.txt

CMD kctf_drop_privs /home/user/healthcheck_loop.sh & /home/user/healthz_webserver.py
