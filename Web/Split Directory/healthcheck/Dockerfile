FROM gcr.io/kctf-docker/healthcheck@sha256:8aedadc9e6354b67bfec45938eea03e7a55ecc5917c82cbae56f2abf557059d2
COPY healthcheck.py solve.py flag.txt /home/user/
CMD ["sh", "-c", "exec kctf_drop_privs python3 /home/user/healthcheck.py"]
